"""Image validation and metadata removal for staged submission uploads."""

from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from tourist03.settings import Settings


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
FORMAT_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


class SubmissionMediaError(ValueError):
    """A public-safe media validation error."""


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    thumbnail: bytes
    mime_type: str
    extension: str
    width: int
    height: int


def _open_verified(data: bytes, settings: Settings) -> tuple[str, int, int]:
    if not data:
        raise SubmissionMediaError("Файл пуст")
    if len(data) > settings.submission_max_image_bytes:
        raise SubmissionMediaError("Файл превышает допустимый размер")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                image_format = str(probe.format or "").upper()
                width, height = probe.size
                probe.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
        raise SubmissionMediaError("Файл не является допустимым изображением") from exc
    if image_format not in ALLOWED_FORMATS:
        raise SubmissionMediaError("Поддерживаются только JPEG, PNG и WebP")
    if width <= 0 or height <= 0 or width * height > settings.submission_max_image_pixels:
        raise SubmissionMediaError("Разрешение изображения превышает допустимое")
    return image_format, width, height


def prepare_submission_image(data: bytes, settings: Settings) -> PreparedImage:
    image_format, width, height = _open_verified(data, settings)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                clean = ImageOps.exif_transpose(source)
                clean.load()
                if image_format == "JPEG":
                    clean = clean.convert("RGB")
                elif clean.mode not in {"RGB", "RGBA", "L", "LA"}:
                    clean = clean.convert("RGBA" if "transparency" in source.info else "RGB")

                content_buffer = BytesIO()
                save_options = {"optimize": True}
                if image_format == "JPEG":
                    save_options["quality"] = 88
                elif image_format == "WEBP":
                    save_options["quality"] = 88
                clean.save(content_buffer, format=image_format, **save_options)

                thumbnail_image = clean.copy()
                thumbnail_image.thumbnail((640, 640), Image.Resampling.LANCZOS)
                if thumbnail_image.mode not in {"RGB", "RGBA"}:
                    thumbnail_image = thumbnail_image.convert("RGB")
                thumbnail_buffer = BytesIO()
                thumbnail_image.save(thumbnail_buffer, format="WEBP", quality=82, method=4)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
        raise SubmissionMediaError("Не удалось безопасно обработать изображение") from exc

    return PreparedImage(
        content=content_buffer.getvalue(),
        thumbnail=thumbnail_buffer.getvalue(),
        mime_type=FORMAT_CONTENT_TYPES[image_format],
        extension=FORMAT_EXTENSIONS[image_format],
        width=width,
        height=height,
    )


def store_prepared_image(prepared: PreparedImage, settings: Settings) -> tuple[str, str, str]:
    relative_dir = Path("submissions") / "staged"
    target_dir = Path(settings.upload_dir).resolve() / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = secrets.token_hex(20)
    safe_filename = f"{stem}{prepared.extension}"
    thumb_filename = f"{stem}.thumb.webp"
    relative_storage = (relative_dir / safe_filename).as_posix()
    relative_thumb = (relative_dir / thumb_filename).as_posix()
    target = target_dir / safe_filename
    thumb_target = target_dir / thumb_filename
    temp = target.with_suffix(target.suffix + ".tmp")
    thumb_temp = thumb_target.with_suffix(thumb_target.suffix + ".tmp")
    try:
        temp.write_bytes(prepared.content)
        thumb_temp.write_bytes(prepared.thumbnail)
        os.replace(temp, target)
        os.replace(thumb_temp, thumb_target)
    except Exception:
        for path in (temp, thumb_temp, target, thumb_target):
            path.unlink(missing_ok=True)
        raise
    return relative_storage, relative_thumb, safe_filename


def safe_storage_path(settings: Settings, storage_key: str) -> Path | None:
    upload_root = Path(settings.upload_dir).resolve()
    candidate = (upload_root / str(storage_key or "")).resolve()
    try:
        candidate.relative_to(upload_root)
    except ValueError:
        return None
    return candidate


def remove_stored_media(settings: Settings, *storage_keys: str | None) -> None:
    for storage_key in storage_keys:
        if not storage_key:
            continue
        path = safe_storage_path(settings, storage_key)
        if path:
            path.unlink(missing_ok=True)
