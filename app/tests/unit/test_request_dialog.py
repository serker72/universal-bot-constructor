"""Тесты логики диалога заявки (валидация, агрегация) без Telegram."""

from datetime import date, time

from app.bot.dialogs.request_dialog import (
    collect_request_data,
    validate_request_data,
)


def _manager_stub(dialog_data: dict, use_time: bool, use_end_date: bool):
    """Заглушка DialogManager с dialog_data и start_data-флагами."""

    class Manager:
        def __init__(self, data: dict, flags: dict) -> None:
            self.dialog_data = data
            self.start_data = flags

    return Manager(
        dialog_data,
        {
            "is_use_time_in_request": use_time,
            "is_use_end_date_in_request": use_end_date,
        },
    )


def test_validate_end_date_before_start_date():
    data = {"start_date": "2026-09-20", "end_date": "2026-09-19"}
    assert validate_request_data(data) is not None


def test_validate_end_time_before_start_time_same_date():
    data = {
        "start_date": "2026-09-20",
        "start_hour": 14,
        "start_min": 30,
        "end_date": "2026-09-20",
        "end_hour": 10,
        "end_min": 0,
    }
    assert validate_request_data(data) is not None


def test_validate_equal_datetimes_ok():
    data = {
        "start_date": "2026-09-20",
        "start_hour": 14,
        "start_min": 30,
        "end_date": "2026-09-20",
        "end_hour": 14,
        "end_min": 30,
    }
    assert validate_request_data(data) is None


def test_validate_end_after_start_ok():
    data = {
        "start_date": "2026-09-20",
        "end_date": "2026-09-21",
        "start_hour": 23,
        "start_min": 55,
        "end_hour": 0,
        "end_min": 5,
    }
    assert validate_request_data(data) is None


def test_validate_dates_only_ok():
    assert validate_request_data({"start_date": "2026-09-20"}) is None
    assert (
        validate_request_data({"start_date": "2026-09-20", "end_date": "2026-09-20"})
        is None
    )


def test_collect_all_fields():
    manager = _manager_stub(
        {
            "phone": "+79991234567",
            "comment": "Комментарий",
            "start_date": "2026-09-20",
            "start_hour": 14,
            "start_min": 30,
            "end_date": "2026-09-21",
            "end_hour": 18,
            "end_min": 0,
        },
        use_time=True,
        use_end_date=True,
    )
    payload = collect_request_data(manager)
    assert payload == {
        "phone": "+79991234567",
        "comment": "Комментарий",
        "start_date": date(2026, 9, 20),
        "start_time": time(14, 30),
        "end_date": date(2026, 9, 21),
        "end_time": time(18, 0),
    }


def test_collect_without_time_flag():
    """is_use_time=False → время не собирается, даже если есть в dialog_data."""
    manager = _manager_stub(
        {
            "phone": "+79991234567",
            "start_date": "2026-09-20",
            "start_hour": 14,
            "start_min": 30,
        },
        use_time=False,
        use_end_date=False,
    )
    payload = collect_request_data(manager)
    assert payload["start_date"] == date(2026, 9, 20)
    assert payload["start_time"] is None
    assert payload["end_date"] is None
    assert payload["end_time"] is None


def test_collect_end_date_without_time():
    """Конечная дата есть, время окончания — нет (is_use_time=False)."""
    manager = _manager_stub(
        {
            "phone": "+79991234567",
            "start_date": "2026-09-20",
            "end_date": "2026-09-21",
            "end_hour": 18,
        },
        use_time=False,
        use_end_date=True,
    )
    payload = collect_request_data(manager)
    assert payload["end_date"] == date(2026, 9, 21)
    assert payload["end_time"] is None
