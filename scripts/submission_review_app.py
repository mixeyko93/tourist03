"""Database-free HTTP shell used only by the placement review artifact."""

from app import create_app
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import submissions as submission_repo
from tourist03.services import submissions as submission_service
from tourist03.settings import Settings


catalog_repo.list_place_types = lambda: []
catalog_repo.list_entity_kinds = lambda **_kwargs: []
catalog_repo.list_entity_types = lambda **_kwargs: []
catalog_repo.list_entity_schemas = lambda **_kwargs: []
catalog_repo.list_public_amenities = lambda: []
catalog_repo.list_public_places = lambda **kwargs: {
    "items": [],
    "total": 0,
    "limit": kwargs.get("limit", 50),
    "offset": kwargs.get("offset", 0),
}
catalog_repo.list_public_entities = catalog_repo.list_public_places
catalog_repo.list_public_catalog_facets = lambda **_kwargs: {
    "entity_kinds": [],
    "subtypes": [],
    "regions": [],
    "districts": [],
    "cities": [],
    "seasonality": [],
    "amenities": [],
}
submission_repo.create_draft = lambda **_kwargs: {
    "public_number": "TUR-REVIEW-SHELL",
    "draft_expires_at": "2026-07-24T12:00:00Z",
    "content_version": 1,
    "source": "review",
}
submission_repo.patch_draft = lambda *_args, **_kwargs: {
    "public_number": "TUR-REVIEW-SHELL",
    "status": "draft",
    "content_version": 2,
    "updated_at": "2026-07-17T12:00:00Z",
}
submission_service.log_crm_audit_event = lambda **_kwargs: None


app = create_app(
    Settings(
        environment="test",
        feature_placement_submissions=True,
        public_base_url="https://review.turistika.example",
        session_secret_key="placement-review-session-secret",
    )
)
