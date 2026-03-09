from tourist03.db import _db_conn
from tourist03.security import _get_user_by_phone, _get_user_by_phone_email


def list_users():
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, role, email, email_verified, phone_verified, created_at
            FROM auth.users
            ORDER BY id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def find_users_for_registration(phone: str, email: str):
    with _db_conn("auth") as conn:
        if email:
            rows = _get_user_by_phone_email(conn, phone, email)
        else:
            row = _get_user_by_phone(conn, phone)
            rows = [row] if row else []
        return [dict(row) for row in rows if row]


def update_pending_user(user_id: int, name: str, email: str, terms_version: str) -> int:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        if email:
            cur.execute(
                """
                UPDATE auth.users
                SET name=%s, email=%s, phone_verified=FALSE, email_verified=FALSE
                WHERE id=%s
                RETURNING id
                """,
                (name, email, user_id),
            )
        else:
            cur.execute(
                """
                UPDATE auth.users
                SET name=%s, email=NULL, phone_verified=FALSE, email_verified=FALSE
                WHERE id=%s
                RETURNING id
                """,
                (name, user_id),
            )
        updated_id = cur.fetchone()["id"]
        cur.execute(
            """
            UPDATE auth.users
            SET terms_accepted_at=NOW(), terms_version=%s
            WHERE id=%s
            """,
            (terms_version, updated_id),
        )
        conn.commit()
        return updated_id


def create_user(name: str, phone: str, email: str, terms_version: str) -> int:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.users (
                name, phone, email, role,
                phone_verified, email_verified,
                terms_accepted_at, terms_version
            )
            VALUES (%s, %s, %s, %s, FALSE, FALSE, NOW(), %s)
            RETURNING id
            """,
            (name, phone, email or None, "user", terms_version),
        )
        user_id = cur.fetchone()["id"]
        conn.commit()
        return user_id


def verify_phone(phone: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return dict(row)
        return None


def verify_email(email: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE email=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (email,),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return dict(row)
        return None


def skip_email(phone: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email=NULL, email_verified=FALSE, phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return dict(row)
        return None


def find_user_by_phone(phone: str):
    with _db_conn("auth") as conn:
        row = _get_user_by_phone(conn, phone)
        return dict(row) if row else None


def revoke_token(token: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute("UPDATE auth.user_tokens SET revoked=TRUE WHERE token=%s", (token,))
        conn.commit()


def get_profile(user_id: int):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, phone_verified, email_verified
            FROM auth.users
            WHERE id=%s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def phone_in_use(phone: str, user_id: int) -> bool:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM auth.users WHERE phone=%s AND id<>%s LIMIT 1", (phone, user_id))
        return bool(cur.fetchone())


def email_in_use(email: str, user_id: int) -> bool:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM auth.users WHERE lower(email)=lower(%s) AND id<>%s LIMIT 1", (email, user_id))
        return bool(cur.fetchone())


def update_profile(
    user_id: int,
    name: str,
    phone: str,
    email: str,
    phone_verified: bool,
    email_verified: bool,
):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET name=%s,
                phone=%s,
                email=%s,
                phone_verified=%s,
                email_verified=%s
            WHERE id=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (name, phone or None, email or None, phone_verified, email_verified, user_id),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def verify_profile_phone(user_id: int, phone: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE id=%s AND phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user_id, phone),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return dict(row)
        return None


def verify_profile_email(user_id: int, email: str):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE id=%s AND lower(email)=lower(%s)
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user_id, email),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return dict(row)
        return None
