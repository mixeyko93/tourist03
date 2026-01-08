# bot.py — aiogram v3 (исправлено: parse_mode через DefaultBotProperties)
# /start — инлайн-кнопка WebApp
# Кнопка "Открыть" в меню чата (MenuButtonWebApp)
# Запуск: python bot.py

import asyncio
import logging
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
)
from aiogram.client.default import DefaultBotProperties  # <— ВАЖНО: свойства бота (parse_mode и т.п.)

# ===== загрузка .env =====
load_dotenv()

# ================== НАСТРОЙКИ ==================
BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()  # например: https://your-domain.tld

if not BOT_TOKEN:
    raise RuntimeError("Укажите токен бота в переменной окружения BOT_TOKEN.")
if not WEBAPP_URL:
    raise RuntimeError("Укажите URL мини-приложения в переменной окружения WEBAPP_URL.")

# ================== ЛОГИ ==================
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tourist03.bot")

# ================== РОУТЕР ==================
router = Router()


def webapp_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопка для открытия WebApp."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Турист_03 ⛺️",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "🏕️ <b>Добро пожаловать в Турист03!</b>\n\n"
        "Найди идеальное место для отдыха на природе! 🌲\n\n"
        "<b>Что ты можешь делать:</b>\n"
        "🗺️ Исследовать карту баз отдыха\n"
        "📅 Бронировать номера и дома на нужные даты\n"
        "💰 Смотреть цены и доступность\n"
        "⭐ Изучать фото и характеристики\n\n"
        "<b>Нажми кнопку ниже и начни планировать отпуск!</b>"
    )
    await message.answer(text, reply_markup=webapp_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — открыть мини-приложение\n"
        "/help — помощь"
    )


# ================== ТОЧКА ВХОДА ==================
async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()
    dp.include_router(router)

    # Системная кнопка "Открыть" (как было)
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        )
        logger.info("MenuButtonWebApp установлен.")
    except Exception:
        logger.exception("Не удалось установить MenuButtonWebApp")

    # >>> ДОБАВЬ ВОТ ЭТО: удалить вебхук перед поллингом
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён, перехожу на polling.")
    except Exception:
        logger.exception("Не удалось удалить webhook")

    logger.info("Бот запущен. WebApp URL: %s", WEBAPP_URL)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
