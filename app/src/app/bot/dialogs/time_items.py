"""Генераторы списков времени для виджетов Select (окна выбора времени).

Списки ограничиваются графиком работы точки продаж: доступны только
слоты, попадающие в интервал `begin <= время < end` (границы открытые
сверху — слот 19:00 при графике 09:00–19:00 не предлагается).

Без границ (`begin`/`end` = None) поведение прежнее: 00…23 и все минуты.
"""

from datetime import time

MINUTES_STEP = 5

# Полный набор слотов часа (используется, когда граница не ограничивает час)
_ALL_MINUTES = range(0, 60)


def generate_hours(
    begin: time | None = None, end: time | None = None
) -> list[tuple[str, int]]:
    """Часы графика: [(метка "09"…"18", значение 9…18)].

    Час `h` доступен, если `begin <= h:00 < end`. Для 09:00–19:00 → 09…18.
    Без границ — прежние 00…23.
    """
    if begin is None or end is None:
        return [(f"{h:02d}", h) for h in range(24)]
    return [(f"{h:02d}", h) for h in range(24) if begin <= time(h, 0) < end]


def generate_minutes(
    step: int = MINUTES_STEP,
    *,
    hour: int | None = None,
    begin: time | None = None,
    end: time | None = None,
) -> list[tuple[str, int]]:
    """Минуты с шагом: [(метка "00","05"…, значение 0…55)].

    С обрезкой по границам графика (передаётся выбранный `hour`):
    - в часе начала (`hour == begin.hour`) — минуты `>= begin.minute`;
    - в часе окончания (`hour == end.hour`) — минуты `< end.minute`;
    - в остальных часах — без ограничений.

    Для 09:00–19:00 все часы 09…18 дают полный набор; для 09:30–19:30
    час 09 начинается с 30, час 19 заканчивается на 25.
    """
    if hour is None or begin is None or end is None:
        return [(f"{m:02d}", m) for m in _ALL_MINUTES if m % step == 0]
    low = begin.minute if hour == begin.hour else 0
    high = end.minute if hour == end.hour else 60
    return [
        (f"{m:02d}", m)
        for m in _ALL_MINUTES
        if m % step == 0 and low <= m < high
    ]
