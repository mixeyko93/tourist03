import json

from fastapi import HTTPException

from tourist03.config import logger
from tourist03.db import _db_conn
from tourist03.schemas import SuperAdminCreateAccountRequest, SuperAdminUpdateAccountRequest
from tourist03.security import hash_password


def superadmin_user_history(user_id: int):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, role, phone_verified, email_verified, created_at
            FROM auth.users
            WHERE id = %s
            """,
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="not found")

        cur.execute(
            """
            SELECT id, event_type, payload, created_at
            FROM auth.user_events
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        events = [dict(row) for row in cur.fetchall()]

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        bookings = [dict(row) for row in cur.fetchall()]

    user_data = dict(user)
    if not user_data.get("email_verified"):
        user_data["email"] = ""

    return {"user": user_data, "bookings": bookings, "events": events, "payments": []}


def superadmin_list_camps():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, lake_name, status
            FROM catalog.camps
            ORDER BY id
            """
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def create_camp_admin_account(payload: SuperAdminCreateAccountRequest):
    email = payload.email.lower().strip()
    display_name = (payload.display_name or "").strip() or email
    password_raw = (payload.password or "").strip()
    if not password_raw:
        raise HTTPException(status_code=400, detail="Пароль не может быть пустым")

    logger.info("Запрос на создание учётки управляющего: email=%s, camps=%s", email, payload.camp_ids)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id
                FROM auth.camp_admin_accounts
                WHERE email = %s
                """,
                (email,),
            )
            existing = cur.fetchone()
            if existing:
                logger.warning("Попытка создать дубликат учётки для email=%s", email)
                raise HTTPException(status_code=400, detail="Учётная запись с таким логином уже существует")

            password_hash = hash_password(password_raw)
            cur.execute(
                """
                INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (email, password_hash, display_name),
            )
            row = cur.fetchone()
            admin_id = row["id"]

            linked: set[int] = set()
            for camp_id in payload.camp_ids:
                try:
                    camp_int = int(camp_id)
                except (ValueError, TypeError):
                    continue
                if camp_int in linked:
                    continue
                linked.add(camp_int)
                cur.execute(
                    """
                    INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                    VALUES (%s, %s)
                    """,
                    (admin_id, camp_int),
                )

            conn.commit()
            logger.info("Учётка управляющего создана: id=%s, email=%s", admin_id, email)
            return {"status": "ok", "admin_id": admin_id}
        except HTTPException:
            conn.rollback()
            logger.exception("Ошибка валидации при создании учётки email=%s", email)
            raise
        except Exception:
            conn.rollback()
            logger.exception("Техническая ошибка при создании учётки email=%s", email)
            raise


def update_camp_admin_account(account_id: int, payload: SuperAdminUpdateAccountRequest):
    email = payload.email.lower().strip() if payload.email is not None else None
    display_name = (payload.display_name or "").strip() if payload.display_name is not None else None
    password_raw = (payload.password or "").strip() if payload.password is not None else None
    is_active = payload.is_active
    camp_ids = payload.camp_ids if payload.camp_ids is not None else None

    if email is not None and not email:
        raise HTTPException(status_code=400, detail="Email не может быть пустым")
    if display_name is not None and not display_name:
        raise HTTPException(status_code=400, detail="Имя управляющего не может быть пустым")

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, email, display_name, is_active
                FROM auth.camp_admin_accounts
                WHERE id=%s
                """,
                (account_id,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Учётная запись не найдена")

            updates = []
            params = []

            if email is not None and email != (existing.get("email") or "").lower().strip():
                cur.execute(
                    """
                    SELECT 1
                    FROM auth.camp_admin_accounts
                    WHERE lower(email) = lower(%s) AND id <> %s
                    """,
                    (email, account_id),
                )
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Учётная запись с таким email уже существует")
                updates.append("email=%s")
                params.append(email)

            if display_name is not None and display_name != (existing.get("display_name") or ""):
                updates.append("display_name=%s")
                params.append(display_name)

            if password_raw is not None and password_raw:
                updates.append("password_hash=%s")
                params.append(hash_password(password_raw))

            if is_active is not None and bool(is_active) != bool(existing.get("is_active")):
                updates.append("is_active=%s")
                params.append(bool(is_active))

            if updates:
                params.append(account_id)
                cur.execute(f"UPDATE auth.camp_admin_accounts SET {', '.join(updates)} WHERE id=%s", tuple(params))

            if camp_ids is not None:
                cur.execute("DELETE FROM crm.camp_admin_links WHERE admin_id=%s", (account_id,))
                linked: set[int] = set()
                for camp_id in camp_ids:
                    try:
                        camp_int = int(camp_id)
                    except (ValueError, TypeError):
                        continue
                    if camp_int in linked:
                        continue
                    linked.add(camp_int)
                    cur.execute(
                        """
                        INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                        VALUES (%s, %s)
                        """,
                        (account_id, camp_int),
                    )

            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            logger.exception("Техническая ошибка при обновлении учётки id=%s", account_id)
            raise

    logger.info("Учётка управляющего обновлена: id=%s", account_id)
    return {"ok": True}


def superadmin_list_accounts():
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email,
                a.display_name,
                a.is_active,
                a.created_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'camp_id', l.camp_id,
                            'camp_name', c.name
                        )
                        ORDER BY c.name
                    ) FILTER (WHERE l.camp_id IS NOT NULL),
                    '[]'::json
                ) AS camps
            FROM auth.camp_admin_accounts AS a
            LEFT JOIN crm.camp_admin_links AS l ON l.admin_id = a.id
            LEFT JOIN catalog.camps AS c ON c.id = l.camp_id
            GROUP BY a.id
            ORDER BY a.created_at DESC, a.id DESC
            """
        )
        rows = cur.fetchall()
    accounts = []
    for row in rows:
        raw_camps = row.get("camps")
        camps_data = []
        if isinstance(raw_camps, str):
            try:
                camps_data = json.loads(raw_camps)
            except Exception:
                camps_data = []
        elif isinstance(raw_camps, list):
            camps_data = raw_camps
        accounts.append(
            {
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "camps": camps_data,
            }
        )
    return accounts
