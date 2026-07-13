"""
Модели базы данных.
SQLite + SQLAlchemy (async) — достаточно для старта, легко мигрировать на Postgres.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Subscription(Base):
    """
    Подписка пользователя на направление.
    Работает и для 'нет билетов, жду появления', и для 'есть билет, слежу за ценой'
    — разница только в значении last_price.
    """
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, index=True)

    origin: Mapped[str] = mapped_column(String(3))          # IATA код, напр. MOW
    destination: Mapped[str] = mapped_column(String(3))     # IATA код, напр. ASB
    depart_date: Mapped[str] = mapped_column(String(10))    # YYYY-MM-DD
    return_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # None = билетов ещё не было найдено, ждём появления
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchLog(Base):
    """Лог поисков — полезно для аналитики популярных направлений."""
    __tablename__ = "search_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, index=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    found_results: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
