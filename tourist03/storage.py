import re
from pathlib import Path
from typing import Optional

from tourist03.config import BASE_DIR, UPLOAD_DIR


def _slug_latin(s: str) -> str:
    s = (s or "").strip()
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
        "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
        "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    out = []
    for ch in s.lower():
        out.append(table.get(ch, ch))
    slug = "".join(out)
    slug = "".join(c for c in slug if c.isalnum() or c in "-_ ")
    return re.sub(r"\s+", "-", slug).strip("-") or "noname"


def _normalize_move(url: str, camp_id: int, room_db_id: Optional[int] = None, camp_name: Optional[str] = None, room_name: Optional[str] = None) -> str:
    if not url or not url.startswith("/static/uploads/"):
        return url

    path = Path(url.lstrip("/"))
    if "uploads/temp/" not in str(path.as_posix()):
        return url

    base = Path(UPLOAD_DIR)
    base.mkdir(parents=True, exist_ok=True)

    camp_slug = _slug_latin(camp_name or f"camp-{camp_id}")
    dst = base / f"{camp_id}_{camp_slug}"

    if room_db_id is not None:
        room_slug = _slug_latin(room_name or f"room-{room_db_id}")
        dst = dst / f"{camp_id}-{room_db_id}_{room_slug}"

    dst.mkdir(parents=True, exist_ok=True)

    src = Path(url.lstrip("/"))
    new_path = dst / src.name
    try:
        new_path.write_bytes(src.read_bytes())
        src.unlink(missing_ok=True)
    except Exception:
        pass

    rel_path = new_path.relative_to(Path(BASE_DIR))
    return "/" + rel_path.as_posix()


def _room_photos_from_fs(camp_id: int, room_id: int, camp_name: Optional[str] = None) -> list[dict]:
    try:
        base = Path(UPLOAD_DIR)
        if not base.exists():
            return []

        camp_slug = _slug_latin(camp_name or f"camp-{camp_id}")
        camp_dir = base / f"{camp_id}_{camp_slug}"
        if not camp_dir.exists():
            matches = sorted([path for path in base.glob(f"{camp_id}_*") if path.is_dir()])
            camp_dir = matches[0] if matches else camp_dir
        if not camp_dir.exists():
            return []

        room_dirs = sorted([path for path in camp_dir.glob(f"{camp_id}-{room_id}_*") if path.is_dir()])
        if not room_dirs:
            return []

        room_dir = room_dirs[0]
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif"):
            files.extend(sorted(room_dir.glob(ext)))
        files = [path for path in files if path.is_file()]
        if not files:
            return []

        out = []
        for idx, path in enumerate(files[:5]):
            rel_path = path.relative_to(Path(BASE_DIR))
            out.append({"url": "/" + rel_path.as_posix(), "cover": idx == 0, "sort": idx})
        return out
    except Exception:
        return []


def _int(val, default=0):
    try:
        if val is None or val == "":
            return default
        return int(val)
    except Exception:
        return default
