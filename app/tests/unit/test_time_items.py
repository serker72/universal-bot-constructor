"""Тесты генераторов списков времени (app.bot.dialogs.time_items).

Проверяются:
- полный набор часов 00–23 и минут с шагом 5 по умолчанию;
- ограничение часов графиком работы точки `generate_hours(begin, end)`;
- обрезка минут по границам графика и при шаге 15.
"""

from datetime import time

from app.bot.dialogs.time_items import generate_hours, generate_minutes


def test_generate_hours():
    hours = generate_hours()
    assert len(hours) == 24
    assert hours[0] == ("00", 0)
    assert hours[12] == ("12", 12)
    assert hours[-1] == ("23", 23)


def test_generate_hours_schedule_09_19():
    """График 09:00–19:00 → часы 09…18 (19 не включается)."""
    hours = generate_hours(time(9, 0), time(19, 0))
    assert len(hours) == 10
    assert hours[0] == ("09", 9)
    assert hours[-1] == ("18", 18)


def test_generate_hours_schedule_10_18():
    """График 10:00–18:00 → часы 10…17."""
    hours = generate_hours(time(10, 0), time(18, 0))
    assert len(hours) == 8
    assert hours[0] == ("10", 10)
    assert hours[-1] == ("17", 17)


def test_generate_hours_partial_begin():
    """Начало с 09:30 — час 09 доступен (09:30 <= 09:00 < 19:00 — ложь,
    но begin <= 09:00 → False, значит 09 не включается)."""
    hours = generate_hours(time(9, 30), time(19, 0))
    # begin=09:30, час 09 → 09:30 <= 09:00 — False → 09 не включается
    assert hours[0] == ("10", 10)
    assert len(hours) == 9


def test_generate_hours_full_day():
    """Начало 00:00 — все 24 часа (без ограничения конца)."""
    hours = generate_hours(time(0, 0), None)
    assert len(hours) == 24


def test_generate_minutes_default_step_5():
    minutes = generate_minutes()
    assert len(minutes) == 12
    assert minutes[0] == ("00", 0)
    assert minutes[1] == ("05", 5)
    assert minutes[-1] == ("55", 55)


def test_generate_minutes_custom_step():
    minutes = generate_minutes(step=15)
    assert minutes == [("00", 0), ("15", 15), ("30", 30), ("45", 45)]


def test_generate_minutes_labels_two_digits():
    """Все метки минут — двухсимвольные («00», «05»)."""
    for label, _ in generate_minutes():
        assert len(label) == 2


def test_generate_minutes_cutting_begin():
    """Час начала: begin.minute=30, шаг 5 → минуты 30,35,40,45,50,55."""
    minutes = generate_minutes(
        step=5, hour=9, begin=time(9, 30), end=time(19, 0)
    )
    assert minutes == [("30", 30), ("35", 35), ("40", 40), ("45", 45), ("50", 50), ("55", 55)]


def test_generate_minutes_cutting_end():
    """Час окончания 19: end.minute=25, шаг 5 → минуты 00,05,10,15,20 (25 не включается)."""
    minutes = generate_minutes(
        step=5, hour=19, begin=time(9, 0), end=time(19, 25)
    )
    assert minutes == [("00", 0), ("05", 5), ("10", 10), ("15", 15), ("20", 20)]


def test_generate_minutes_cutting_both():
    """Начало 09:30, конец 19:15, час 19 → минуты 00,05,10"""
    minutes = generate_minutes(
        step=5, hour=19, begin=time(9, 30), end=time(19, 15)
    )
    assert minutes == [("00", 0), ("05", 5), ("10", 10)]


def test_generate_minutes_no_cutting_middle_hour():
    """Час не на границах — все минуты с шагом."""
    minutes = generate_minutes(step=5, hour=12, begin=time(9, 0), end=time(19, 0))
    assert len(minutes) == 12
    assert minutes[0] == ("00", 0)
    assert minutes[-1] == ("55", 55)


def test_generate_minutes_step_15_cutting():
    """Шаг 15: обрезка по begin.minute=20 → 20,30,40,50."""
    minutes = generate_minutes(
        step=15, hour=9, begin=time(9, 20), end=time(19, 0)
    )
    # Шаг 15: 0,15,30,45; begin.minute=20 → >=20: 30,45
    assert minutes == [("30", 30), ("45", 45)]


def test_generate_minutes_without_bounds():
    """Без begin/end — без обрезки."""
    minutes = generate_minutes(step=10, hour=9, begin=None, end=None)
    assert minutes == [("00", 0), ("10", 10), ("20", 20), ("30", 30), ("40", 40), ("50", 50)]


def test_generate_minutes_hour_none():
    """hour=None — без обрезки."""
    minutes = generate_minutes(step=5, hour=None, begin=time(9, 0), end=time(19, 0))
    assert len(minutes) == 12
