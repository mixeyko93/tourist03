from fastapi import APIRouter

from tourist03.services import bot_webhook as bot_webhook_service

router = APIRouter()

router.add_api_route(
    "/api/bot/tg-link",
    bot_webhook_service.api_bot_tg_link,
    methods=["POST"],
)
