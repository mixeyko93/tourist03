from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from tourist03.config import STAFF_BOT_TOKEN
from tourist03.security import link_admin_telegram_account


class TgLinkRequest(BaseModel):
    code: str
    init_data: str


def _verify_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """Проверяет подпись Telegram WebApp initData, возвращает распарсенные поля или None."""
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        hash_value = parsed.pop("hash", None)
        if not hash_value:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, hash_value):
            return None

        return parsed
    except Exception:
        return None


def api_bot_tg_link(payload: TgLinkRequest):
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Код привязки не передан")

    if not STAFF_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Бот не настроен на сервере")

    fields = _verify_telegram_init_data(payload.init_data, STAFF_BOT_TOKEN)
    if not fields:
        raise HTTPException(status_code=401, detail="Подпись Telegram не прошла проверку")

    user_str = fields.get("user", "")
    try:
        user = json.loads(user_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось разобрать данные пользователя Telegram")

    tg_user_id = int(user.get("id", 0))
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="Telegram user_id не найден")

    # chat_id для личного чата совпадает с user_id
    tg_chat_id = tg_user_id
    tg_username = user.get("username") or None

    linked = link_admin_telegram_account(
        code,
        telegram_user_id=tg_user_id,
        telegram_chat_id=tg_chat_id,
        telegram_username=tg_username,
    )

    if not linked:
        raise HTTPException(status_code=400, detail="Код привязки не найден или истёк. Сгенерируйте новый в CRM.")

    return {
        "ok": True,
        "display_name": linked.get("display_name") or linked.get("email") or "Сотрудник",
    }
