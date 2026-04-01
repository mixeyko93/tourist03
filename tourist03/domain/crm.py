STAFF_ROLE_KEYS = (
    "chief_manager",
    "administrator",
    "booking_manager",
    "content_manager",
    "finance_manager",
    "viewer",
)

STAFF_ROLE_LABELS = {
    "chief_manager": "Главный управляющий",
    "administrator": "Администратор",
    "booking_manager": "Менеджер бронирований",
    "content_manager": "Контент-менеджер",
    "finance_manager": "Финансист",
    "viewer": "Только просмотр",
}

STAFF_PERMISSION_KEYS = (
    "manage_staff_accounts",
    "manage_staff_permissions",
    "manage_shift_schedule",
    "manage_camp_visibility",
    "manage_pricing",
    "manage_cancellation_policy",
    "manage_rooms",
    "manage_services",
    "manage_templates",
    "manage_notifications",
    "manage_bookings",
    "manage_payments",
    "view_audit_log",
    "export_data",
)

STAFF_PERMISSION_LABELS = {
    "manage_staff_accounts": "Управление учётками сотрудников",
    "manage_staff_permissions": "Управление правами сотрудников",
    "manage_shift_schedule": "Управление графиком смен",
    "manage_camp_visibility": "Управление публикацией и видимостью базы",
    "manage_pricing": "Управление ценами",
    "manage_cancellation_policy": "Управление правилами отмены",
    "manage_rooms": "Управление апартаментами",
    "manage_services": "Управление услугами",
    "manage_templates": "Управление шаблонами уведомлений",
    "manage_notifications": "Управление уведомлениями",
    "manage_bookings": "Управление бронированиями",
    "manage_payments": "Управление оплатами",
    "view_audit_log": "Просмотр журнала действий",
    "export_data": "Экспорт данных",
}

DEFAULT_ROLE_PERMISSIONS = {
    "chief_manager": STAFF_PERMISSION_KEYS,
    "administrator": (
        "manage_staff_accounts",
        "manage_staff_permissions",
        "manage_shift_schedule",
        "manage_camp_visibility",
        "manage_pricing",
        "manage_cancellation_policy",
        "manage_rooms",
        "manage_services",
        "manage_templates",
        "manage_notifications",
        "manage_bookings",
        "manage_payments",
        "view_audit_log",
        "export_data",
    ),
    "booking_manager": (
        "manage_bookings",
        "manage_payments",
        "manage_notifications",
        "view_audit_log",
        "export_data",
    ),
    "content_manager": (
        "manage_rooms",
        "manage_services",
        "manage_templates",
        "manage_camp_visibility",
        "view_audit_log",
    ),
    "finance_manager": (
        "manage_payments",
        "view_audit_log",
        "export_data",
    ),
    "viewer": ("view_audit_log",),
}

SENSITIVE_CHANGE_KINDS = (
    "archive",
    "camp_visibility",
    "pricing",
    "cancellation_policy",
    "shift_schedule",
)

SENSITIVE_CHANGE_LABELS = {
    "archive": "Архивирование",
    "camp_visibility": "Публикация и скрытие базы",
    "pricing": "Изменение цен",
    "cancellation_policy": "Изменение правил отмены",
    "shift_schedule": "Изменение графика смен",
}

CHANGE_REQUEST_STATUS_KEYS = (
    "pending_review",
    "approved",
    "rejected",
    "needs_clarification",
    "applied_with_responsibility",
    "rolled_back",
)

CHANGE_REQUEST_STATUS_LABELS = {
    "pending_review": "На подтверждении",
    "approved": "Подтверждено",
    "rejected": "Отклонено",
    "needs_clarification": "Нужно уточнение",
    "applied_with_responsibility": "Применено под ответственность",
    "rolled_back": "Откат выполнен",
}

EVENT_CENTER_STATUS_KEYS = ("new", "viewed", "in_progress", "closed")

EVENT_CENTER_STATUS_LABELS = {
    "new": "Новое",
    "viewed": "Просмотрено",
    "in_progress": "В работе",
    "closed": "Закрыто",
}

NOTIFICATION_CHANNEL_KEYS = ("in_app", "telegram", "browser", "sound")

NOTIFICATION_CHANNEL_LABELS = {
    "in_app": "Внутри системы",
    "telegram": "Telegram",
    "browser": "Браузерное уведомление",
    "sound": "Звуковой сигнал",
}

SERVICE_STATUS_KEYS = ("draft", "active", "hidden", "sold_out", "paused", "archived")

SERVICE_STATUS_LABELS = {
    "draft": "Черновик",
    "active": "Активна",
    "hidden": "Скрыта",
    "sold_out": "Нет мест",
    "paused": "Остановлена",
    "archived": "Архив",
}

BOOKING_STATUS_UI_LABELS = {
    "pending": "Новая заявка",
    "awaiting_confirmation": "Ожидает подтверждения",
    "awaiting_payment": "Ожидает оплаты",
    "confirmed": "Подтверждена",
    "checked_in": "Заселён",
    "completed": "Завершена",
    "no_show": "Не заехал",
    "cancelled_by_user": "Отменена гостем",
    "cancelled": "Отменена базой",
    "cancelled_by_base": "Отменена базой",
    "rejected": "Отклонена",
    "expired_pending": "Просрочена без ответа",
}

PAYMENT_STATUS_UI_LABELS = {
    "unpaid": "Не оплачено",
    "awaiting_prepayment": "Требуется предоплата",
    "partially_paid": "Частично оплачено",
    "paid": "Оплачено полностью",
    "cash": "Оплата на месте",
    "refund_partial": "Возврат частично",
    "refund_full": "Возврат полностью",
    "awaiting_refund": "Ожидает возврата",
    "failed": "Платёж не прошёл",
    "chargeback": "Спор / чарджбэк",
    "overpaid": "Переплата",
}

TEMPLATE_KEYS = (
    "booking_new",
    "booking_confirmed",
    "booking_payment_requested",
    "booking_cancelled",
    "arrival_instructions",
    "checkout_reminder",
    "followup_message",
)
