"""
Фоновый воркер: периодически проверяет все активные подписки,
сравнивает с последней известной ценой и шлёт уведомления при изменениях.

Запускать отдельным процессом: python worker.py
(либо через APScheduler внутри того же процесса, что и bot.py —
 но раздельные процессы проще масштабировать и не блокируют друг друга)
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import BOT_TOKEN, DATABASE_URL, CHECK_INTERVAL_SECONDS
from models import Subscription
from travelpayouts_api import search_cheap_tickets, TURKMENISTAN_DESTINATIONS
from cards import format_ticket_card, ticket_keyboard

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)

engine = create_async_engine(DATABASE_URL)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def check_subscription(session, sub: Subscription):
    tickets = await search_cheap_tickets(
        sub.origin, sub.destination, sub.depart_date, sub.return_date
    )

    if not tickets:
        # билетов по-прежнему нет — просто обновляем время проверки
        sub.last_checked_at = datetime.utcnow()
        return

    best = tickets[0]  # самый дешёвый найденный вариант

    should_notify = False
    notify_reason = ""

    if sub.last_price is None:
        # билетов не было — теперь появились
        should_notify = True
        notify_reason = "появились билеты"
    elif best.price < sub.last_price:
        # цена упала
        should_notify = True
        notify_reason = "цена снизилась"
    # если цена выросла или не изменилась — молчим, не спамим пользователя

    if should_notify:
        dest_name = TURKMENISTAN_DESTINATIONS.get(sub.destination, sub.destination)
        prefix = (
            f"🎉 По направлению {sub.origin} → {dest_name} появились билеты!\n\n"
            if notify_reason == "появились билеты"
            else f"📉 Цена на {sub.origin} → {dest_name} снизилась!\n\n"
        )
        try:
            await bot.send_message(sub.chat_id, prefix)
            await bot.send_message(
                sub.chat_id,
                format_ticket_card(best),
                reply_markup=ticket_keyboard(best),
                parse_mode="HTML",
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить уведомление chat_id={sub.chat_id}: {e}")

    sub.last_price = best.price
    sub.last_checked_at = datetime.utcnow()


async def check_all_subscriptions():
    async with Session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.is_active == True)  # noqa: E712
        )
        subs = result.scalars().all()

        logging.info(f"Проверяю {len(subs)} активных подписок")

        for sub in subs:
            try:
                await check_subscription(session, sub)
            except Exception as e:
                logging.error(f"Ошибка при проверке подписки {sub.id}: {e}")
            await asyncio.sleep(1)  # не долбим API Travelpayouts слишком часто подряд

        await session.commit()


async def main_loop():
    while True:
        await check_all_subscriptions()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main_loop())
