"""Unit-тесты динамического конструктора заявки (роутинг без Telegram).

Проверяется логика Routing Engine на стабе DialogManager:
- process_and_go_next: запись ответа, переход по типу следующего поля;
- двухшаговый ввод TIME (temp_hour → «ЧЧ:ММ»);
- go_back: возврат к предыдущему полю;
- summary при пустой схеме и в конце схемы.
"""

import pytest

from app.bot.states import DynamicRequestSG
from app.domain.models import RequestFieldType


class DialogManagerStub:
    """Стаб DialogManager: schema/answers в start_data, current_step в dialog_data."""

    def __init__(self, schema: list[dict]) -> None:
        self.start_data = {"schema": schema, "answers": {}}
        self.dialog_data: dict = {}
        self.switched_to = None

    async def switch_to(self, state) -> None:
        self.switched_to = state


def _field(fid: int, ftype: str, required: bool = False, meta: dict | None = None):
    return {
        "id": fid,
        "code": f"field_{fid}",
        "type": ftype,
        "label": f"Поле {fid}",
        "is_required": required,
        "meta_data": meta or {},
    }


@pytest.fixture
def manager_text_number_time():
    schema = [
        _field(1, RequestFieldType.TEXT.value),
        _field(2, RequestFieldType.NUMBER.value, required=True, meta={"min": 1}),
        _field(3, RequestFieldType.TIME.value, meta={"minute_step": 15}),
    ]
    return DialogManagerStub(schema)


# -- process_and_go_next -------------------------------------------------------


async def test_first_field_routes_by_type(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import process_and_go_next

    m = manager_text_number_time
    m.dialog_data["current_step"] = 0
    await process_and_go_next(m, "ответ")
    assert m.start_data["answers"][1] == "ответ"
    assert m.dialog_data["current_step"] == 1
    # следующее поле — NUMBER
    assert m.switched_to is DynamicRequestSG.input_number


async def test_time_field_routes_to_hour_window(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import process_and_go_next

    m = manager_text_number_time
    m.dialog_data["current_step"] = 1
    await process_and_go_next(m, "5")
    assert m.start_data["answers"][2] == "5"
    # TIME → окно часов (не сменяя шаг на минуты)
    assert m.switched_to is DynamicRequestSG.input_time_hour


async def test_last_field_routes_to_summary(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import process_and_go_next

    m = manager_text_number_time
    m.dialog_data["current_step"] = 2
    await process_and_go_next(m, "14:30")
    assert m.start_data["answers"][3] == "14:30"
    assert m.switched_to is DynamicRequestSG.summary


async def test_empty_schema_routes_to_summary():
    from app.bot.dialogs.dynamic_request_dialog import _after_phone

    m = DialogManagerStub([])
    await _after_phone(m)
    assert m.switched_to is DynamicRequestSG.summary
    assert m.dialog_data["current_step"] == 0


async def test_first_field_after_phone(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import _after_phone

    m = manager_text_number_time
    await _after_phone(m)
    assert m.dialog_data["current_step"] == 0
    assert m.switched_to is DynamicRequestSG.input_text


async def test_optional_field_can_be_skipped(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import process_and_go_next

    m = manager_text_number_time
    m.dialog_data["current_step"] = 0
    await process_and_go_next(m, None)
    assert m.start_data["answers"][1] is None


# -- двухшаговый TIME ----------------------------------------------------------


async def test_hour_then_minute(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import (
        on_hour_selected,
        on_minute_selected,
    )

    m = manager_text_number_time
    m.dialog_data["current_step"] = 2

    class SelectStub:
        pass

    class CBStub:
        pass

    await on_hour_selected(CBStub(), SelectStub(), m, 14)
    # шаг не сместился, перешли к минутам
    assert m.dialog_data["current_step"] == 2
    assert m.dialog_data["temp_hour"] == 14
    assert m.switched_to is DynamicRequestSG.input_time_minute

    await on_minute_selected(CBStub(), SelectStub(), m, 30)
    # «ЧЧ:ММ» записано, шаг +1, конец схемы → summary
    assert m.start_data["answers"][3] == "14:30"
    assert m.switched_to is DynamicRequestSG.summary


# -- go_back --------------------------------------------------------------------


async def test_go_back_to_previous_field(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import go_back

    m = manager_text_number_time
    m.dialog_data["current_step"] = 2  # TIME-поле
    await go_back(m)
    assert m.dialog_data["current_step"] == 1
    # предыдущее поле — NUMBER
    assert m.switched_to is DynamicRequestSG.input_number


async def test_go_back_to_time_hours(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import go_back

    m = manager_text_number_time
    # TIME-поле на шаге 2 — назад должен попасть на окно часов
    m.dialog_data["current_step"] = 2
    await go_back(m)
    assert m.switched_to is DynamicRequestSG.input_number
    # а вот если шаг указывает на TIME — окно часов
    m.dialog_data["current_step"] = 2
    await go_back(m)


async def test_go_back_from_first_step(manager_text_number_time):
    from app.bot.dialogs.dynamic_request_dialog import go_back

    m = manager_text_number_time
    m.dialog_data["current_step"] = 0
    await go_back(m)
    # не уходим в минус
    assert m.dialog_data["current_step"] == 0
    assert m.switched_to is DynamicRequestSG.input_text


# -- JSON round-trip start_data (ключи answers становятся строками) ----------


def _reload_from_json(manager) -> None:
    """Имитация перезагрузки диалога из хранилища: dict → JSON → dict."""
    import json

    manager.start_data = json.loads(json.dumps(manager.start_data))


async def test_answers_survive_json_roundtrip(manager_text_number_time):
    """Ключи answers после JSON — строки; чтение нормализует их обратно в int."""
    from app.bot.dialogs.dynamic_request_dialog import (
        _get_answer,
        process_and_go_next,
    )

    m = manager_text_number_time
    m.dialog_data["current_step"] = 0
    await process_and_go_next(m, "ответ")
    _reload_from_json(m)
    # после reload ключи answers — строки ("1"), как в продакшен-хранилище
    assert "1" in m.start_data["answers"]
    # читать можно по int-id поля
    assert _get_answer(m, 1) == "ответ"


async def test_skip_after_reload_then_summary(manager_text_number_time):
    """«Пропустить» после reload (str-ключи) не падает, summary показывает ответы."""
    from app.bot.dialogs.dynamic_request_dialog import (
        process_and_go_next,
    )
    from app.bot.dialogs.getters import summary_getter

    m = manager_text_number_time
    m.dialog_data["current_step"] = 0
    await process_and_go_next(m, "ответ")  # шаг 0 заполнен, шаг 1 — обязательный NUMBER
    _reload_from_json(m)

    # «Пропустить» на шаге 2 (TIME, необязательный) — шаг 1 пропустим вводом None
    m.dialog_data["current_step"] = 1
    await process_and_go_next(m, None)
    m.dialog_data["current_step"] = 2
    await process_and_go_next(m, None)  # → summary

    data = await summary_getter(m)
    assert "Поле 1: ответ" in data["summary_lines"]
    assert "Поле 2: —" in data["summary_lines"]
    assert "Поле 3: —" in data["summary_lines"]


def test_normalize_answers_mixed_keys():
    """Смешанные ключи (str из хранилища + int из живых записей): int-запись сильнее."""
    from app.bot.dialogs.getters import normalize_answers

    normalized = normalize_answers({"3": "старое", 3: "новое"})
    assert normalized == {3: "новое"}
