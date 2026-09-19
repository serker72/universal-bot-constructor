"""Единые тексты статусов заявки для бота.

Используется: keyboards (эмодзи для кнопок), handlers/requests (текст в
карточке заявки), notifications (уведомления посетителю при смене статуса).
"""

STATUS_EMOJI = {
    "new": "🆕",
    "approved": "✅",
    "rejected": "❌",
    "completed": "🏁",
    "cancelled_by_customer": "🚫",
}

STATUS_TEXT = {
    "new": "🆕 Новая",
    "approved": "✅ Подтверждена",
    "rejected": "❌ Отменена менеджером",
    "completed": "🏁 Выполнена",
    "cancelled_by_customer": "🚫 Отменена вами",
}

# Уведомления посетителю при смене статуса (консьюмер, notifications.py)
STATUS_NOTIFY_TEXT = {
    "approved": "✅ Ваша заявка #{request_id} подтверждена менеджером.",
    "rejected": "❌ Ваша заявка #{request_id} отклонена менеджером.",
    "completed": "🏁 Заявка #{request_id} выполнена. Спасибо за обращение!",
}
