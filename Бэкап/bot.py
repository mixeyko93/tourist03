import os
import json
import asyncio
import aiohttp
import socket

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

from aiogram.types import WebAppData
from aiogram.types import MenuButtonWebApp

from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import TCPConnector

from dotenv import load_dotenv




load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL") or "https://example.com"
API_BASE = os.getenv("API_BASE") or "http://127.0.0.1:8080"
PROXY_URL = os.getenv("PROXY_URL")  # например: socks5://127.0.0.1:1080 или http://user:pass@proxy:8080

dp = Dispatcher()

@dp.message(CommandStart())
async def on_start(m: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Открыть карту", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )
    await m.answer(
        "Привет! Нажми «Открыть карту», выбери базу и даты. "
        "Когда нажмёшь «Отправить заявку» в мини-приложении, я оформлю бронь.",
        reply_markup=kb
    )

@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    try:
        payload = json.loads(m.web_app_data.data)  # {"room_id":..,"date_from":..,"..."}
    except Exception:
        await m.answer("Не понял данные из мини-приложения 🤔")
        return

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(f"{API_BASE}/api/bookings", json=payload, timeout=30) as resp:
                if resp.status != 200:
                    await m.answer(f"Не удалось создать бронь: {await resp.text()}")
                    return
                data = await resp.json()
    except Exception as e:
        await m.answer(f"Ошибка подключения к API: {e}")
        return

    bid = data.get("id")
    await m.answer(
        f"✅ Заявка создана!\nНомер #{bid}\nДаты: {data.get('date_from')} — {data.get('date_to')}\nСтатус: {data.get('status')}"
    )

async def build_bot() -> Bot:
    """
    Создаём бота ТОЛЬКО после старта event loop.
    Форсим IPv4 + увеличенный таймаут. Если указан PROXY_URL — используем прокси.
    """
    if PROXY_URL:
        # если нужен прокси: pip install aiohttp-socks
        from aiohttp_socks import ProxyConnector
        connector = ProxyConnector.from_url(PROXY_URL)
    else:
        connector = TCPConnector(family=socket.AF_INET)  # только IPv4

    session = AiohttpSession(connector=connector, timeout=30)
    return Bot(BOT_TOKEN, session=session)

async def main():
    bot = await build_bot()
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Открыть", web_app=WebAppInfo(url=WEBAPP_URL)))
    print("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
