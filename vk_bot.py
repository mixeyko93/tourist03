from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.exceptions import ApiError, VkApiError
from vk_api.utils import get_random_id


load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tourist03.vk_bot")


WELCOME_TEXT = (
    "🏕️ Добро пожаловать в Турист03!\n\n"
    "Найдите идеальное место для отдыха на природе. В приложении вы можете:\n"
    "🗺️ смотреть карту баз отдыха\n"
    "📅 проверять даты и доступность\n"
    "🏡 выбирать номера и дома\n"
    "💰 смотреть цены и условия бронирования\n\n"
    "Нажмите кнопку ниже и откройте приложение."
)

HELP_TEXT = (
    "Доступные команды:\n"
    "Начать или /start — открыть приложение\n"
    "Помощь или /help — помощь"
)


@dataclass(frozen=True)
class VkBotSettings:
    token: str
    group_id: int
    webapp_url: str


def _read_settings() -> VkBotSettings:
    token = os.getenv("VK_TOKEN", "").strip()
    group_id_raw = os.getenv("VK_GROUP_ID", "").strip()
    webapp_url = (
        os.getenv("TOURIST_WEBAPP_URL", "").strip()
        or os.getenv("WEBAPP_URL", "").strip()
        or "https://turist03.ru"
    )

    if not token:
        raise RuntimeError("Укажите VK_TOKEN в .env для запуска VK-бота.")
    if not group_id_raw:
        raise RuntimeError("Укажите VK_GROUP_ID в .env для запуска VK-бота.")
    try:
        group_id = int(group_id_raw)
    except ValueError as exc:
        raise RuntimeError("VK_GROUP_ID должен быть числом.") from exc
    if not webapp_url:
        raise RuntimeError("Укажите TOURIST_WEBAPP_URL или WEBAPP_URL в .env.")

    return VkBotSettings(
        token=token,
        group_id=group_id,
        webapp_url=webapp_url.rstrip("/"),
    )


def _button_payload(command: str) -> str:
    return json.dumps({"cmd": command}, ensure_ascii=False)


def _main_keyboard(webapp_url: str) -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "open_link",
                        "link": webapp_url,
                        "label": "Турист_03 ⛺️",
                        "payload": _button_payload("open_app"),
                    },
                    "color": "primary",
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Помощь",
                        "payload": _button_payload("help"),
                    },
                    "color": "secondary",
                }
            ],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def _message_from_event(event: Any) -> dict[str, Any]:
    event_obj = getattr(event, "obj", None) or getattr(event, "object", None) or {}
    if hasattr(event_obj, "message"):
        message = event_obj.message
    elif isinstance(event_obj, dict) and "message" in event_obj:
        message = event_obj["message"]
    else:
        message = event_obj
    if hasattr(message, "items"):
        return dict(message.items())
    return dict(message or {})


def _payload_command(message: dict[str, Any]) -> str:
    raw_payload = message.get("payload")
    if not raw_payload:
        return ""
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("cmd") or "").strip().lower()


def _text_command(message: dict[str, Any]) -> str:
    text = str(message.get("text") or "").strip().lower()
    if text in {"/start", "start", "начать", "старт", "меню"}:
        return "start"
    if text in {"/help", "help", "помощь", "помоги"}:
        return "help"
    return ""


def _send_message(vk_api: Any, *, peer_id: int, text: str, keyboard: str) -> None:
    try:
        vk_api.messages.send(
            peer_id=int(peer_id),
            message=text,
            keyboard=keyboard,
            random_id=get_random_id(),
            dont_parse_links=1,
        )
    except (ApiError, VkApiError):
        logger.exception("VK API не смог отправить сообщение peer_id=%s", peer_id)
    except Exception:
        logger.exception("Неожиданная ошибка отправки VK-сообщения peer_id=%s", peer_id)


def _handle_message(vk_api: Any, message: dict[str, Any], *, keyboard: str) -> None:
    peer_id = int(message.get("peer_id") or message.get("from_id") or 0)
    if not peer_id:
        logger.warning("VK-сообщение без peer_id: %s", message)
        return

    command = _payload_command(message) or _text_command(message)
    if command == "help":
        _send_message(vk_api, peer_id=peer_id, text=HELP_TEXT, keyboard=keyboard)
        return

    _send_message(vk_api, peer_id=peer_id, text=WELCOME_TEXT, keyboard=keyboard)


def run() -> None:
    settings = _read_settings()
    vk_session = VkApi(token=settings.token)
    vk_api = vk_session.get_api()
    keyboard = _main_keyboard(settings.webapp_url)

    logger.info(
        "VK-бот Tourist03 запущен. group_id=%s, webapp=%s",
        settings.group_id,
        settings.webapp_url,
    )

    while True:
        try:
            longpoll = VkBotLongPoll(vk_session, settings.group_id)
            for event in longpoll.listen():
                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue
                try:
                    _handle_message(vk_api, _message_from_event(event), keyboard=keyboard)
                except Exception:
                    logger.exception("Ошибка обработки входящего VK-сообщения")
        except KeyboardInterrupt:
            logger.info("VK-бот остановлен.")
            raise
        except Exception:
            logger.exception("VK Long Poll завершился с ошибкой. Перезапуск через 5 секунд.")
            time.sleep(5)


if __name__ == "__main__":
    run()
