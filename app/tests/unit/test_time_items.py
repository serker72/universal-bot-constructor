"""Тесты генераторов списков времени (app.bot.dialogs.time_items)."""

from app.bot.dialogs.time_items import generate_hours, generate_minutes


def test_generate_hours():
    hours = generate_hours()
    assert len(hours) == 24
    assert hours[0] == ("00", 0)
    assert hours[12] == ("12", 12)
    assert hours[-1] == ("23", 23)


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
