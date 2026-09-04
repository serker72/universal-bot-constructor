"""Ключи и состояния FSM бота."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Регистрация посетителя: ФИО → телефон → согласие."""

    full_name = State()
    phone = State()
    consent = State()


class RequestStates(StatesGroup):
    """Создание заявки: телефон → комментарий."""

    phone = State()
    comment = State()

