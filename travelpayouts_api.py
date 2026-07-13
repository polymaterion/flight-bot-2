"""
Обёртка над Travelpayouts Data API.
Документация: https://travelpayouts.github.io/slate/#flights_2
"""
import httpx
from datetime import date
from dataclasses import dataclass

from config import TRAVELPAYOUTS_TOKEN as TOKEN, TRAVELPAYOUTS_MARKER as MARKER
BASE_URL = "https://api.travelpayouts.com"

# Города/аэропорты Туркменистана (IATA)
TURKMENISTAN_DESTINATIONS = {
    "ASB": "Ашхабад",
    "CRZ": "Туркменабад",
    "MYP": "Мары",
    "DYU": "Дашогуз",       # уточнить код при интеграции
    "KRW": "Туркменбаши",
}


@dataclass
class Ticket:
    origin: str
    destination: str
    depart_date: str
    return_date: str | None
    price: float
    airline: str
    transfers: int
    found_at: str  # когда цена была зафиксирована в базе TP


async def search_cheap_tickets(
    origin: str,
    destination: str,
    depart_date: str | None = None,
    return_date: str | None = None,
) -> list[Ticket]:
    """
    Поиск по кэшу цен Travelpayouts (/v1/prices/cheap).
    Возвращает уже найденные другими пользователями цены — не live-поиск.
    Если depart_date не задан — вернёт самые дешёвые варианты за ближайшие месяцы.
    """
    params = {
        "origin": origin,
        "destination": destination,
        "token": TOKEN,
        "currency": "rub",
    }
    if depart_date:
        params["depart_date"] = depart_date[:7]  # API принимает YYYY-MM для группировки
    if return_date:
        params["return_date"] = return_date[:7]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/v1/prices/cheap", params=params)
        resp.raise_for_status()
        data = resp.json()

    tickets: list[Ticket] = []
    if not data.get("success"):
        return tickets

    dest_data = data.get("data", {}).get(destination, {})
    for date_key, info in dest_data.items():
        tickets.append(
            Ticket(
                origin=origin,
                destination=destination,
                depart_date=info.get("departure_at", date_key),
                return_date=info.get("return_at"),
                price=info.get("price"),
                airline=info.get("airline", "—"),
                transfers=info.get("transfers", 0),
                found_at=info.get("found_at", ""),
            )
        )

    tickets.sort(key=lambda t: t.price)
    return tickets


def build_affiliate_link(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None = None,
    sub_id: str = "bot",
) -> str:
    """
    Формирует партнёрскую ссылку на поиск Aviasales.
    Формат дат в URL: DDMM (без года, Aviasales сам подставит ближайший подходящий год)
    Пример итогового пути: ASB1509MOW2209
    """
    def fmt(d: str) -> str:
        y, m, day = d.split("-")
        return f"{day}{m}"

    path = f"{origin}{fmt(depart_date)}{destination}"
    if return_date:
        path += fmt(return_date)
    path += "1"  # 1 пассажир

    return (
        f"https://www.aviasales.ru/search/{path}"
        f"?marker={MARKER}_{sub_id}"
    )
