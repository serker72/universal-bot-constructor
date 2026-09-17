"""Генераторы списков времени для виджетов Select (окна выбора времени)."""

MINUTES_STEP = 5


def generate_hours() -> list[tuple[str, int]]:
    """Часы 00–23: [(метка "00"…"23", значение 0…23)]."""
    return [(f"{h:02d}", h) for h in range(24)]


def generate_minutes(step: int = MINUTES_STEP) -> list[tuple[str, int]]:
    """Минуты с заданным шагом: [(метка "00","05"…, значение 0…55)]."""
    return [(f"{m:02d}", m) for m in range(0, 60, step)]
