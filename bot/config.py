"""Настройки бота из переменных окружения (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Минимальный загрузчик .env без внешних зависимостей."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Service:
    id: str
    title: str
    minutes: int
    price: int


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    db_path: Path
    tz: timezone
    open_hour: int = 10
    close_hour: int = 20
    slot_minutes: int = 30
    booking_days_ahead: int = 7
    remind_before: timedelta = timedelta(hours=2)
    services: tuple[Service, ...] = field(
        default=(
            Service("cut", "Мужская стрижка", 60, 600),
            Service("beard", "Оформление бороды", 30, 350),
            Service("combo", "Стрижка + борода", 90, 850),
            Service("kids", "Детская стрижка", 45, 450),
        )
    )

    def service(self, service_id: str) -> Service:
        return next(s for s in self.services if s.id == service_id)


def load_settings() -> Settings:
    _load_dotenv()
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN — скопируйте .env.example в .env и вставьте токен от @BotFather")
    admins = frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
    offset = int(os.getenv("TIMEZONE_OFFSET", "2"))
    return Settings(
        bot_token=token,
        admin_ids=admins,
        db_path=Path(os.getenv("DB_PATH", "data/barberbook.sqlite3")),
        tz=timezone(timedelta(hours=offset)),
    )
