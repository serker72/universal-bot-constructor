"""Ключи и состояния FSM бота."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Регистрация посетителя: ФИО → телефон → согласие."""

    full_name = State()
    phone = State()
    consent = State()


class PointStates(StatesGroup):
    """Выбор точки продаж (селектор).

    Источник истины о выбранной точке — колонка visitors.point_id;
    состояние используется только как маркер «режим выбора», чтобы
    скрыть меню пока пользователь не выбрал филиал.
    """

    choose = State()


class DynamicRequestSG(StatesGroup):
    """Создание заявки (динамический конструктор, aiogram-dialog).

    Состояния — по ТИПУ поля, а не по полю (aiogram-dialog требует
    статического набора состояний). Порядок прохождения задаётся
    массивом schema в start_data + current_step в dialog_data:
    телефон → поля схемы (text/number/date/time_hour+time_minute/
    select) → summary.

    TIME-поле занимает два окна: input_time_hour → input_time_minute
    (без сдвига current_step между ними).
    """

    input_phone = State()
    input_text = State()
    input_number = State()
    input_date = State()
    input_time_hour = State()
    input_time_minute = State()
    input_select = State()
    input_multiselect = State()
    input_boolean = State()
    summary = State()

