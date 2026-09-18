"""Тесты логики диалога заявки (валидация, агрегация) без Telegram."""

import pytest

from app.bot.states import RequestStates
from datetime import date, time

from app.bot.dialogs.request_dialog import (
    _to_comment_or_fix_dates,
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


# -- переход к комментарию с валидацией дат ---------------------------------


class EventStub:
    """Заглушка CallbackQuery: фиксирует answer()."""

    def __init__(self) -> None:
        self.answer_args: tuple | None = None
        self.answer_kwargs: dict | None = None

    async def answer(self, *args, **kwargs) -> None:
        self.answer_args = args
        self.answer_kwargs = kwargs


class SwitchManager:
    """Заглушка DialogManager: фиксирует switch_to()."""

    def __init__(self, dialog_data: dict) -> None:
        self.dialog_data = dialog_data
        self.switched_to: list = []

    async def switch_to(self, state) -> None:
        self.switched_to.append(state)


@pytest.mark.asyncio
async def test_to_comment_skipped_on_invalid_dates():
    """Ошибочные даты → алерт и возврат на окно даты окончания."""
    manager = SwitchManager(
        {"start_date": "2026-09-20", "end_date": "2026-09-19"}
    )
    event = EventStub()

    await _to_comment_or_fix_dates(manager, event)

    assert event.answer_kwargs == {"show_alert": True}
    assert manager.switched_to == [RequestStates.end_date]


@pytest.mark.asyncio
async def test_to_comment_proceeds_on_valid_dates():
    """Корректные даты → переход к окну комментария, без алерта."""
    manager = SwitchManager(
        {"start_date": "2026-09-20", "end_date": "2026-09-21"}
    )
    event = EventStub()

    await _to_comment_or_fix_dates(manager, event)

    assert event.answer_args is None
    assert manager.switched_to == [RequestStates.input_comment]
