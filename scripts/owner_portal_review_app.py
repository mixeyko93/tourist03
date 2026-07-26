"""Database-free Owner Portal shell for screenshots and Lighthouse."""

from __future__ import annotations

from app import create_app
from tourist03.owner_security import get_current_owner
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import owners as owner_repo
from tourist03.services import owners as owner_service
from tourist03.security import get_superadmin
from tourist03.settings import Settings


OWNER = {
    "id": 32,
    "email": "mikhail.owner@example.test",
    "display_name": "Михаил Соколов",
    "company": "Байкальские истории",
    "phone": "+7 999 120-34-56",
    "telegram": "https://t.me/baikal_story",
    "whatsapp": "https://wa.me/79991203456",
    "max": "https://max.ru/baikal_story",
    "preferred_contact_type": "telegram",
    "account_status": "active",
    "two_factor_status": "disabled",
    "last_login": "2026-07-26T08:45:00Z",
    "created_at": "2025-11-02T11:30:00Z",
}
CAMP = {
    "id": 81,
    "name": "Эко-отель «Сосны Байкала»",
    "slug": "sosny-baikala",
    "place_type_id": 2,
    "short_description": "Тихий эко-отель на первой линии Байкала.",
    "description": "Домики среди сосен, собственный пляж и маршруты для прогулок. " * 3,
    "region": "Республика Бурятия",
    "district": "Прибайкальский район",
    "city": "Гремячинск",
    "locality": "Турка",
    "address": "Береговая улица, 12",
    "lat": 52.9532,
    "lng": 108.221,
    "min_price": 6500,
    "seasonality": "Круглый год",
    "working_hours": "Ежедневно, 09:00–21:00",
    "surroundings": "Сосновый лес, берег Байкала и экотропа рядом.",
    "video_urls": [],
    "publication_status": "published",
    "status": "active",
    "confirmed_at": "2026-07-22T10:00:00Z",
    "updated_at": "2026-07-25T12:15:00Z",
    "content_version": 7,
    "contacts": [
        {"contact_type": "phone", "label": "Телефон", "value": "+7 999 120-34-56", "url": "tel:+79991203456", "is_public": True, "sort_order": 10},
        {"contact_type": "telegram", "label": "Telegram", "value": "https://t.me/baikal_story", "url": "https://t.me/baikal_story", "is_public": True, "sort_order": 20},
    ],
    "amenities": [{"amenity_id": 1, "value": None}, {"amenity_id": 2, "value": None}, {"amenity_id": 8, "value": None}],
    "rooms": [
        {"id": 401, "name": "Семейный дом", "room_type": "Дом", "capacity": 4, "price": 9500, "description": "Две спальни, терраса и вид на озеро."},
        {"id": 402, "name": "Студия в лесу", "room_type": "Студия", "capacity": 2, "price": 6500, "description": ""},
    ],
    "media": [
        {"id": 1, "media_type": "image", "url": "/static/uploads/1_angir/20251101-010251370896.jpg", "cover": True, "sort": 0},
        {"id": 2, "media_type": "image", "url": "/static/uploads/1_angir/20251101-010251378895.jpg", "cover": False, "sort": 1},
        {"id": 3, "media_type": "image", "url": "/static/uploads/1_angir/20251101-010251395580.jpg", "cover": False, "sort": 2},
    ],
}
AMENITIES = [
    {"id": 1, "name": "Wi-Fi", "category": "Связь"},
    {"id": 2, "name": "Парковка", "category": "Транспорт"},
    {"id": 5, "name": "Можно с животными", "category": "Правила"},
    {"id": 8, "name": "Пляж", "category": "Природа"},
    {"id": 10, "name": "Баня", "category": "Отдых"},
    {"id": 16, "name": "Детская площадка", "category": "Семья"},
]
CHANGE = {
    "id": 170,
    "public_number": "CHG-2026-BA1KA1",
    "camp_id": 81,
    "camp_name": CAMP["name"],
    "camp_slug": CAMP["slug"],
    "owner_account_id": OWNER["id"],
    "owner_name": OWNER["display_name"],
    "owner_email": OWNER["email"],
    "status": "in_review",
    "status_label": "На проверке",
    "content_version": 3,
    "base_content_version": 7,
    "proposed_payload": {
        "short_description": "Эко-отель для семейного отдыха на первой линии Байкала.",
        "min_price": 6900,
        "video_urls": ["https://rutube.ru/video/1234567890abcdef/"],
    },
    "published_snapshot": CAMP,
    "diff_payload": [
        {"field": "short_description", "label": "Краткое описание", "before": CAMP["short_description"], "after": "Эко-отель для семейного отдыха на первой линии Байкала."},
        {"field": "min_price", "label": "Минимальная цена", "before": 6500, "after": 6900},
        {"field": "video_urls", "label": "Видео", "before": [], "after": ["https://rutube.ru/video/1234567890abcdef/"]},
    ],
    "moderator_comment": None,
    "created_at": "2026-07-25T11:00:00Z",
    "updated_at": "2026-07-26T08:20:00Z",
    "submitted_at": "2026-07-25T12:00:00Z",
    "decided_at": None,
    "history": [
        {"id": 2, "summary": "Изменения взяты на проверку", "new_status": "in_review", "created_at": "2026-07-26T08:20:00Z"},
        {"id": 1, "summary": "Изменения отправлены на проверку", "new_status": "submitted", "created_at": "2026-07-25T12:00:00Z"},
    ],
    "staged_media": [],
}
APPLIED_CHANGE = {
    **CHANGE,
    "id": 164,
    "public_number": "CHG-2026-7F21D0AA",
    "status": "applied",
    "status_label": "Опубликовано",
    "moderator_comment": "Контакты и описание подтверждены.",
    "submitted_at": "2026-07-18T09:20:00Z",
    "decided_at": "2026-07-19T14:05:00Z",
}


def _quality():
    return {
        "score": 76,
        "earned_weight": 76,
        "total_weight": 100,
        "checklist": [
            {"key": "name", "complete": True, "label": "Есть название", "weight": 8},
            {"key": "description", "complete": True, "label": "Есть подробное описание", "weight": 10},
            {"key": "coordinates", "complete": True, "label": "Есть координаты", "weight": 5},
            {"key": "photos", "complete": False, "label": "Добавьте ещё 3 фотографии", "weight": 12},
            {"key": "videos", "complete": False, "label": "Добавьте видео", "weight": 5},
            {"key": "room_descriptions", "complete": False, "label": "Добавьте описание вариантов размещения", "weight": 5},
        ],
        "recommendations": [
            "Добавьте ещё 3 фотографии",
            "Добавьте видео",
            "Добавьте описание вариантов размещения",
            "Добавьте WhatsApp",
            "Добавьте MAX",
        ],
        "health": [
            {"key": "photos", "level": "warning", "label": "Добавьте актуальные фото"},
            {"key": "contacts", "level": "good", "label": "Контакты заполнены"},
            {"key": "coordinates", "level": "good", "label": "Координаты проверены"},
            {"key": "videos", "level": "warning", "label": "Видео отсутствует"},
            {"key": "prices", "level": "good", "label": "Цены заполнены"},
            {"key": "rooms", "level": "danger", "label": "Нет описания комнат"},
        ],
    }


owner_service.get_current_owner = lambda _request: OWNER
owner_service.get_superadmin = lambda _request: {
    "id": 1,
    "login": "reviewer",
    "display_name": "Анна Модератор",
    "is_root": True,
}
owner_repo.list_owner_camps = lambda _owner_id: [
    {
        "id": CAMP["id"],
        "name": CAMP["name"],
        "slug": CAMP["slug"],
        "place_type_name": "Эко-отель",
        "publication_status": "published",
        "status": "active",
        "updated_at": CAMP["updated_at"],
        "confirmed_at": CAMP["confirmed_at"],
        "role_key": "primary_owner",
        "is_primary": True,
        "pending_changes": 1,
    }
]
owner_repo.get_camp_snapshots = lambda _ids: {CAMP["id"]: CAMP}
owner_repo.get_camp_snapshot = lambda _camp_id: CAMP
owner_repo.owner_profile_statistics = lambda _owner_id: {
    "objects_count": 1,
    "approved_changes": 7,
    "pending_changes": 1,
    "rejected_changes": 1,
}
owner_repo.list_owner_changes = lambda _owner_id, camp_id=None: [CHANGE, APPLIED_CHANGE]
owner_repo.list_owner_activity = lambda _owner_id, limit=30: [
    {"id": 8, "created_at": "2026-07-26T08:20:00Z", "type": "owner_change_in_review", "description": "Изменения взяты на проверку", "camp_id": 81, "action_url": "/owner/changes/170"},
    {"id": 7, "created_at": "2026-07-25T12:00:00Z", "type": "owner_change_submitted", "description": "Изменения отправлены на проверку", "camp_id": 81, "action_url": "/owner/changes/170"},
    {"id": 6, "created_at": "2026-07-19T14:05:00Z", "type": "owner_change_applied", "description": "Изменения опубликованы", "camp_id": 81, "action_url": "/owner/changes/164"},
]
owner_repo.list_owner_notifications = lambda _owner_id, limit=30: []
owner_repo.owner_can_access_camp = lambda _owner_id, _camp_id: True
owner_repo.create_owner_change = lambda _owner_id, _camp_id: ({**CHANGE, "status": "draft", "status_label": "Черновик", "diff_payload": [], "proposed_payload": {}, "content_version": 1}, True)
owner_repo.save_owner_change = lambda change_id, owner_id, proposed_payload, expected_version: {
    **CHANGE,
    "id": change_id,
    "status": "draft",
    "status_label": "Черновик",
    "proposed_payload": proposed_payload,
    "content_version": expected_version + 1,
    "diff_payload": [
        {"field": "name", "label": "Название", "before": CAMP["name"], "after": proposed_payload.get("name", CAMP["name"])},
        {"field": "short_description", "label": "Краткое описание", "before": CAMP["short_description"], "after": proposed_payload.get("short_description", CAMP["short_description"])},
    ],
    "staged_media": [],
}
owner_repo.get_owner_change = lambda change_id, owner_id=None: {**CHANGE, "id": change_id}
owner_repo.list_moderation_changes = lambda **_kwargs: [CHANGE, APPLIED_CHANGE]
owner_repo.list_owner_accounts = lambda: [{**OWNER, "is_active": True, "camps": [{"camp_id": 81, "camp_name": CAMP["name"], "role_key": "primary_owner", "is_primary": True}]}]
catalog_repo.list_public_amenities = lambda: AMENITIES


app = create_app(
    Settings(
        environment="test",
        feature_owner_portal=True,
        feature_owner_change_requests=True,
        public_base_url="https://review.turistika.example",
        session_secret_key="owner-review-session-secret-at-least-32-characters",
    )
)
app.dependency_overrides[get_current_owner] = lambda: OWNER
app.dependency_overrides[get_superadmin] = lambda: {
    "id": 1,
    "login": "reviewer",
    "display_name": "Анна Модератор",
    "is_root": True,
}
