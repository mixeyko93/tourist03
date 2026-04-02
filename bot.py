from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo

from tourist03.config import CRM_BASE_URL, STAFF_BOT_POLL_INTERVAL, STAFF_BOT_TOKEN
from tourist03.repositories import notifications as notification_repo
from tourist03.services import admin as admin_service
from tourist03.services.staff_bot import (
    build_staff_rollback_confirm_keyboard,
    build_staff_event_keyboard,
    build_staff_start_text,
    deliver_pending_telegram_notifications,
    enqueue_booking_escalations,
    format_staff_event_message,
    format_staff_events_digest,
    get_staff_open_events_for_chat,
    link_staff_account_by_code,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

if not BOT_TOKEN and not STAFF_BOT_TOKEN:
    raise RuntimeError("Укажите токен клиентского или staff-бота в переменных окружения.")
if BOT_TOKEN and not WEBAPP_URL:
    raise RuntimeError("Укажите URL мини-приложения в переменной окружения WEBAPP_URL.")

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tourist03.bot")

user_router = Router()
staff_router = Router()


def _extract_command_arg(text: str | None) -> str:
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Турист_03 ⛺️",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )


def crm_button(action_url: str = "/events") -> InlineKeyboardMarkup:
    base_url = (CRM_BASE_URL or "https://crm.turist03.ru").rstrip("/")
    normalized = action_url if action_url.startswith("/") else f"/{action_url}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть CRM",
                    url=f"{base_url}{normalized}",
                )
            ]
        ]
    )


def _staff_account_for_chat(chat_id: int):
    return notification_repo.get_staff_account_by_chat_id(int(chat_id))


@user_router.message(CommandStart())
async def user_cmd_start(message: Message) -> None:
    text = (
        "🏕️ <b>Добро пожаловать в Турист03!</b>\n\n"
        "Найди идеальное место для отдыха на природе. В мини-приложении вы можете:\n"
        "🗺️ смотреть карту баз отдыха\n"
        "📅 проверять даты и доступность\n"
        "🏡 выбирать номера и дома\n"
        "💰 смотреть цены и условия бронирования\n\n"
        "<b>Нажмите кнопку ниже и откройте приложение.</b>"
    )
    await message.answer(text, reply_markup=webapp_keyboard())


@user_router.message(Command("help"))
async def user_cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — открыть мини-приложение\n"
        "/help — помощь"
    )


async def _handle_staff_link(message: Message, code: str) -> None:
    if not code:
        await message.answer(
            "Нужен код привязки из CRM.\n\n"
            "Откройте карточку сотрудника, выпустите код и отправьте сюда команду вида:\n"
            "<code>/link ВАШ_КОД</code>"
        )
        return

    linked = link_staff_account_by_code(
        code,
        telegram_user_id=message.from_user.id if message.from_user else message.chat.id,
        telegram_chat_id=message.chat.id,
        telegram_username=message.from_user.username if message.from_user else None,
    )
    if not linked:
        await message.answer(
            "Код привязки не найден или уже истёк. Сгенерируйте новый код в CRM и повторите попытку."
        )
        return

    staff_label = linked.get("display_name") or linked.get("email") or "Сотрудник"
    await message.answer(
        f"✅ <b>Привязка выполнена</b>\n\n"
        f"{staff_label}, staff-бот подключён к вашей учётке.\n"
        "Теперь вы будете получать уведомления по новым заявкам, сменам и критичным изменениям.",
        reply_markup=crm_button("/events"),
    )


@staff_router.message(CommandStart())
async def staff_cmd_start(message: Message) -> None:
    code = _extract_command_arg(message.text)
    if code:
        await _handle_staff_link(message, code)
        return
    await message.answer(build_staff_start_text(), reply_markup=crm_button())


@staff_router.message(Command("help"))
async def staff_cmd_help(message: Message) -> None:
    await message.answer(build_staff_start_text(), reply_markup=crm_button())


@staff_router.message(Command("link"))
async def staff_cmd_link(message: Message) -> None:
    await _handle_staff_link(message, _extract_command_arg(message.text))


@staff_router.message(Command("events"))
async def staff_cmd_events(message: Message) -> None:
    account, items = get_staff_open_events_for_chat(message.chat.id, limit=5)
    if not account:
        await message.answer(
            "Эта учётка Telegram ещё не связана с CRM.\n\n"
            "Сначала выпустите код привязки в карточке сотрудника и отправьте сюда команду /link."
        )
        return

    if not items:
        await message.answer(format_staff_events_digest(account, items), reply_markup=crm_button("/events"))
        return

    await message.answer(format_staff_events_digest(account, items), reply_markup=crm_button("/events"))
    for item in items[:3]:
        await message.answer(
            text=format_staff_event_message(item),
            reply_markup=build_staff_event_keyboard(item) or crm_button("/events"),
        )


@staff_router.callback_query()
async def staff_callback_router(callback: CallbackQuery) -> None:
    raw = (callback.data or "").strip()
    if not raw.startswith("cr:"):
        await callback.answer()
        return

    account = _staff_account_for_chat(callback.message.chat.id if callback.message else callback.from_user.id)
    if not account:
        await callback.answer("Сначала привяжите staff-бот к своей учётке CRM.", show_alert=True)
        return

    parts = raw.split(":")
    if len(parts) < 3:
        await callback.answer("Некорректная команда.", show_alert=True)
        return

    try:
        if parts[1] == "rollback" and len(parts) >= 4 and parts[2] == "init":
            request_id = int(parts[3])
            if callback.message:
                await callback.message.edit_reply_markup(
                    reply_markup=build_staff_rollback_confirm_keyboard(
                        request_id,
                        action_url=f"/approvals?request_id={request_id}",
                    )
                )
            await callback.answer("Откат вернёт данные к предыдущему состоянию. Подтвердите действие.", show_alert=True)
            return

        if parts[1] == "rollback" and len(parts) >= 4 and parts[2] == "cancel":
            request_id = int(parts[3])
            request_item = admin_service.get_accessible_change_request_for_admin(account, request_id)
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=build_staff_event_keyboard({
                    "event_type": "change_request_applied",
                    "metadata": {"change_request_id": request_id},
                    "action_url": f"/approvals?request_id={request_id}",
                }) or crm_button(f"/approvals?request_id={request_id}"))
            await callback.answer("Откат отменён.")
            return

        action_map = {
            "approve": ("approve", "Изменение подтверждено."),
            "reject": ("reject", "Изменение отклонено."),
            "clarify": ("clarify", "Запрос на уточнение отправлен."),
            "rollback": ("rollback", "Откат подтверждён."),
        }

        if parts[1] == "rollback" and len(parts) >= 4 and parts[2] == "confirm":
            request_id = int(parts[3])
            action_key, success_text = action_map["rollback"]
        else:
            request_id = int(parts[2])
            if parts[1] not in action_map:
                await callback.answer("Неизвестное действие.", show_alert=True)
                return
            action_key, success_text = action_map[parts[1]]

        updated = admin_service.handle_change_request_action_for_admin(
            account,
            request_id,
            action=action_key,
            comment="Подтверждено через staff-бот" if action_key in {"approve", "rollback"} else "Решение принято через staff-бот",
        )
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=crm_button(f"/approvals?request_id={request_id}"))
            await callback.message.answer(
                format_staff_event_message(
                    {
                        "title": updated.get("summary") or "Согласование обновлено",
                        "body": f"{success_text}\nСтатус: {updated.get('status')}",
                        "camp_name": updated.get("camp_name"),
                        "severity": "info",
                        "created_at": updated.get("updated_at"),
                    }
                ),
                reply_markup=crm_button(f"/approvals?request_id={request_id}"),
            )
        await callback.answer(success_text)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or (str(exc).strip() if str(exc).strip() else "Не удалось выполнить действие.")
        await callback.answer(str(detail), show_alert=True)


async def _run_user_bot() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(user_router)

    try:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
            logger.info("Кнопка WebApp для клиентского бота установлена.")
        except Exception:
            logger.exception("Не удалось установить кнопку WebApp для клиентского бота")

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook клиентского бота удалён, перехожу на polling.")
        except Exception:
            logger.exception("Не удалось удалить webhook клиентского бота")

        logger.info("Клиентский бот запущен. WebApp URL: %s", WEBAPP_URL)
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            handle_signals=False,
        )
    finally:
        await bot.session.close()


async def _staff_background_loop(bot: Bot) -> None:
    poll_interval = max(int(STAFF_BOT_POLL_INTERVAL or 60), 10)
    while True:
        try:
            created = enqueue_booking_escalations()
            delivered = await deliver_pending_telegram_notifications(bot)
            if created or delivered:
                logger.info("Staff-бот обработал очередь: создано=%s, отправлено=%s", created, delivered)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Фоновая обработка staff-бота завершилась с ошибкой")
        await asyncio.sleep(poll_interval)


async def _run_staff_bot() -> None:
    bot = Bot(
        token=STAFF_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(staff_router)
    background_task = asyncio.create_task(_staff_background_loop(bot))

    try:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook staff-бота удалён, перехожу на polling.")
        except Exception:
            logger.exception("Не удалось удалить webhook staff-бота")

        logger.info("Staff-бот запущен.")
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            handle_signals=False,
        )
    finally:
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task
        await bot.session.close()


async def main() -> None:
    tasks: list[asyncio.Task] = []
    if BOT_TOKEN:
        tasks.append(asyncio.create_task(_run_user_bot()))
    if STAFF_BOT_TOKEN:
        tasks.append(asyncio.create_task(_run_staff_bot()))
    if not tasks:
        raise RuntimeError("Не найден ни один токен бота для запуска.")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
