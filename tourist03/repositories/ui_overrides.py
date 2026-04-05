from __future__ import annotations

import json
from typing import Any, Optional

from tourist03.db import _db_conn


def get_ui_override(override_key: str) -> Optional[dict[str, Any]]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                key,
                payload,
                updated_by_actor_type,
                updated_by_actor_id,
                updated_by_actor_display,
                updated_at
            FROM crm.ui_overrides
            WHERE key = %s
            """,
            (str(override_key).strip(),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def save_ui_override(
    override_key: str,
    payload: dict[str, Any],
    *,
    actor_type: str,
    actor_id: int | None,
    actor_display: str | None,
) -> dict[str, Any]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.ui_overrides (
                key,
                payload,
                updated_by_actor_type,
                updated_by_actor_id,
                updated_by_actor_display,
                updated_at
            )
            VALUES (%s, %s::jsonb, %s, %s, %s, NOW())
            ON CONFLICT (key)
            DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_by_actor_type = EXCLUDED.updated_by_actor_type,
                updated_by_actor_id = EXCLUDED.updated_by_actor_id,
                updated_by_actor_display = EXCLUDED.updated_by_actor_display,
                updated_at = NOW()
            RETURNING
                key,
                payload,
                updated_by_actor_type,
                updated_by_actor_id,
                updated_by_actor_display,
                updated_at
            """,
            (
                str(override_key).strip(),
                json.dumps(payload or {}, ensure_ascii=False),
                actor_type,
                actor_id,
                actor_display,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return dict(row)
