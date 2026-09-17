"""Ключи и состояния FSM бота."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Регистрация посетителя: ФИО → телефон → согласие."""

    full_name = State()
    phone = State()
    consent = State()


class RequestStates(StatesGroup):
    """Создание заявки (диалог aiogram-dialog).

    Порядок прохождения зависит от флагов настроек
    is_use_time_in_request / is_use_end_date_in_request:
    телефон → начальная дата → (время начала) → (дата окончания)
    → (время окончания) → комментарий.
    """

    input_phone = State()
    start_date = State()
    start_hour = State()
    start_min = State()
    end_date = State()
    end_hour = State()
    end_min = State()
    input_comment = State()

