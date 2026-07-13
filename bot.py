"""
Основная логика бота: поиск, показ карточек, создание подписок.
Запуск: python bot.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import BOT_TOKEN, DATABASE_URL
from models import Base, Subscription, SearchLog
from travelpayouts_api import search_cheap_tickets, TURKMENISTAN_DESTINATIONS
from cards import format_ticket_card, ticket_keyboard, no_results_text, no_results_keyboard

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

engine = create_async_engine(DATABASE_URL)
Session = async_sessionmaker(engine, expire_on_commit=False)


class SearchForm(StatesGroup):
    origin = State()
    destination = State()
    depart_date = State()
    return_date = State()


@dp.startup()
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я помогу найти билеты в Туркменистан.\n\n"
        "Ищу цены через Aviasales.\n\n"
        "Из какого города вы хотите вылететь? Напишите название "
        "или код города (например: Москва или MOW)."
    )
    await state.set_state(SearchForm.origin)


@dp.message(SearchForm.origin)
async def got_origin(message: Message, state: FSMContext):
    # В проде здесь нужен геокодер городов через /v1/city_iata (Travelpayouts autocomplete)
    origin_code = message.text.strip().upper()[:3]
    await state.update_data(origin=origin_code)

    dest_list = "\n".join(f"• {name} ({code})" for code, name in TURKMENISTAN_DESTINATIONS.items())
    await message.answer(f"Куда летим?\n\n{dest_list}\n\nНапишите название города.")
    await state.set_state(SearchForm.destination)


@dp.message(SearchForm.destination)
async def got_destination(message: Message, state: FSMContext):
    dest_code = message.text.strip().upper()[:3]
    await state.update_data(destination=dest_code)
    await message.answer("Дата вылета? Формат: ГГГГ-ММ-ДД (например 2026-09-15)")
    await state.set_state(SearchForm.depart_date)


@dp.message(SearchForm.depart_date)
async def got_depart_date(message: Message, state: FSMContext):
    await state.update_data(depart_date=message.text.strip())
    await message.answer("Дата обратного вылета? Если билет в одну сторону — отправьте «-»")
    await state.set_state(SearchForm.return_date)


@dp.message(SearchForm.return_date)
async def got_return_date(message: Message, state: FSMContext):
    return_date = message.text.strip()
    return_date = None if return_date == "-" else return_date
    await state.update_data(return_date=return_date)

    data = await state.get_data()
    await run_search_and_reply(message, data)
    await state.clear()


async def run_search_and_reply(message: Message, data: dict):
    origin = data["origin"]
    destination = data["destination"]
    depart_date = data["depart_date"]
    return_date = data.get("return_date")

    await message.answer("🔎 Ищу билеты...")

    tickets = await search_cheap_tickets(origin, destination, depart_date, return_date)

    async with Session() as session:
        session.add(SearchLog(
            chat_id=message.chat.id, origin=origin, destination=destination,
            found_results=bool(tickets),
        ))
        await session.commit()

    if not tickets:
        await message.answer(
            no_results_text(origin, destination),
            reply_markup=no_results_keyboard(origin, destination, depart_date, return_date),
        )
        return

    for t in tickets[:5]:  # показываем топ-5 самых дешёвых
        await message.answer(
            format_ticket_card(t),
            reply_markup=ticket_keyboard(t),
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("track:"))
async def create_subscription(callback: CallbackQuery):
    _, origin, destination, depart_date, return_date = callback.data.split(":")
    return_date = None if return_date == "-" else return_date

    async with Session() as session:
        sub = Subscription(
            chat_id=callback.message.chat.id,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            last_price=None,
            last_checked_at=datetime.utcnow(),
        )
        session.add(sub)
        await session.commit()

    dest_name = TURKMENISTAN_DESTINATIONS.get(destination, destination)
    await callback.message.answer(
        f"🔔 Подписка создана: {origin} → {dest_name}, вылет {depart_date}.\n\n"
        f"Я проверяю цены несколько раз в день и пришлю сообщение, "
        f"как только появятся билеты или цена изменится.\n\n"
        f"Посмотреть все подписки: /subscriptions"
    )
    await callback.answer()


@dp.message(F.text == "/subscriptions")
async def list_subscriptions(message: Message):
    async with Session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Subscription).where(
                Subscription.chat_id == message.chat.id,
                Subscription.is_active == True,  # noqa: E712
            )
        )
        subs = result.scalars().all()

    if not subs:
        await message.answer("У вас пока нет активных подписок.")
        return

    lines = ["📋 <b>Ваши подписки:</b>\n"]
    for s in subs:
        dest_name = TURKMENISTAN_DESTINATIONS.get(s.destination, s.destination)
        price_text = f"{s.last_price:,.0f} ₽" if s.last_price else "билетов пока нет"
        lines.append(f"• {s.origin} → {dest_name}, {s.depart_date} — {price_text} (/unsub_{s.id})")

    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.regexp(r"^/unsub_(\d+)$"))
async def unsubscribe(message: Message):
    sub_id = int(message.text.split("_")[1])
    async with Session() as session:
        from sqlalchemy import select
        sub = await session.get(Subscription, sub_id)
        if sub and sub.chat_id == message.chat.id:
            sub.is_active = False
            await session.commit()
            await message.answer("Подписка отключена.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
