"""Форматирование карточек-сообщений и клавиатур."""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from travelpayouts_api import Ticket, build_affiliate_link, TURKMENISTAN_DESTINATIONS


def format_ticket_card(t: Ticket) -> str:
    dest_name = TURKMENISTAN_DESTINATIONS.get(t.destination, t.destination)
    transfers_text = "Прямой рейс" if t.transfers == 0 else f"Пересадок: {t.transfers}"

    text = (
        f"✈️ <b>{t.origin} → {dest_name} ({t.destination})</b>\n\n"
        f"📅 Вылет: {t.depart_date}\n"
    )
    if t.return_date:
        text += f"📅 Обратно: {t.return_date}\n"
    text += (
        f"🏢 {t.airline} · {transfers_text}\n\n"
        f"💰 <b>{t.price:,.0f} ₽</b>\n"
        f"🕓 Цена зафиксирована: {t.found_at[:10] if t.found_at else 'недавно'}\n\n"
        f"⚠️ Уточняйте актуальную цену и наличие мест на сайте — "
        f"кэш цен обновляется не мгновенно."
    )
    return text


def ticket_keyboard(t: Ticket) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    link = build_affiliate_link(t.origin, t.destination, t.depart_date, t.return_date)
    kb.button(text="🛒 Купить на Aviasales", url=link)
    kb.button(
        text="🔔 Следить за ценой",
        callback_data=f"track:{t.origin}:{t.destination}:{t.depart_date}:{t.return_date or '-'}",
    )
    kb.adjust(1)
    return kb.as_markup()


def no_results_text(origin: str, destination: str) -> str:
    dest_name = TURKMENISTAN_DESTINATIONS.get(destination, destination)
    return (
        f"😔 Пока не нашлось билетов {origin} → {dest_name} на эти даты.\n\n"
        f"Это частый случай для Туркменистана — рейсов немного, и цены "
        f"в базе обновляются не по всем датам сразу.\n\n"
        f"Хотите, я буду проверять это направление и пришлю сообщение, "
        f"как только появятся варианты?"
    )


def no_results_keyboard(origin: str, destination: str, depart_date: str, return_date: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="🔔 Создать подписку",
        callback_data=f"track:{origin}:{destination}:{depart_date}:{return_date or '-'}",
    )
    kb.button(text="🔁 Изменить даты", callback_data="new_search")
    kb.adjust(1)
    return kb.as_markup()
