"""Deterministic search, geospatial and recommendation primitives."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


MAX_SEARCH_QUERY_LENGTH = 120
MAX_SEARCH_TOKENS = 16
MAX_SEARCH_VARIANTS = 12
NEARBY_RADII_KM = frozenset({5, 10, 25, 50, 100})
_WHITESPACE_RE = re.compile(r"\s+")

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
_LATIN_TO_CYRILLIC = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("yo", "е"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
    ("a", "а"),
    ("b", "б"),
    ("c", "к"),
    ("d", "д"),
    ("e", "е"),
    ("f", "ф"),
    ("g", "г"),
    ("h", "х"),
    ("i", "и"),
    ("j", "й"),
    ("k", "к"),
    ("l", "л"),
    ("m", "м"),
    ("n", "н"),
    ("o", "о"),
    ("p", "п"),
    ("q", "к"),
    ("r", "р"),
    ("s", "с"),
    ("t", "т"),
    ("u", "у"),
    ("v", "в"),
    ("w", "в"),
    ("x", "кс"),
    ("y", "ы"),
    ("z", "з"),
)


class DiscoveryValidationError(ValueError):
    """A public discovery input is invalid."""


@dataclass(frozen=True)
class SearchTerms:
    original: str
    normalized: str
    variants: tuple[str, ...]
    tokens: tuple[str, ...]


def normalize_search_text(value: object) -> str:
    raw = unicodedata.normalize("NFKC", str(value or "")).lower().replace("ё", "е")
    normalized_chars = [
        character if character.isalnum() else " "
        for character in raw
    ]
    return _WHITESPACE_RE.sub(" ", "".join(normalized_chars)).strip()


def transliterate_to_latin(value: str) -> str:
    normalized = normalize_search_text(value)
    return "".join(_CYRILLIC_TO_LATIN.get(character, character) for character in normalized)


def transliterate_to_cyrillic(value: str) -> str:
    result = normalize_search_text(value)
    if not result or any("а" <= character <= "я" for character in result):
        return result
    for source, target in _LATIN_TO_CYRILLIC:
        result = result.replace(source, target)
    return normalize_search_text(result)


def _synonym_groups(config: Mapping[str, Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    groups: list[tuple[str, ...]] = []
    for key, raw_values in config.items():
        values = []
        for raw in (key, *raw_values):
            normalized = normalize_search_text(raw)
            if normalized and normalized not in values:
                values.append(normalized)
        if len(values) > 1:
            groups.append(tuple(values))
    return tuple(groups)


def build_search_terms(
    value: str,
    synonyms: Mapping[str, Sequence[str]],
) -> SearchTerms:
    original = str(value or "").strip()
    if not original:
        raise DiscoveryValidationError("Введите поисковый запрос")
    if len(original) > MAX_SEARCH_QUERY_LENGTH:
        raise DiscoveryValidationError(
            f"Поисковый запрос не должен быть длиннее {MAX_SEARCH_QUERY_LENGTH} символов"
        )
    normalized = normalize_search_text(original)
    tokens = tuple(normalized.split())
    if not normalized or not tokens:
        raise DiscoveryValidationError("Введите буквы или цифры для поиска")
    if len(tokens) > MAX_SEARCH_TOKENS:
        raise DiscoveryValidationError("Поисковый запрос содержит слишком много слов")

    variants: list[str] = [normalized]
    for transliterated in (
        transliterate_to_latin(normalized),
        transliterate_to_cyrillic(normalized),
    ):
        if transliterated and transliterated != normalized and transliterated not in variants:
            variants.append(transliterated)

    for group in _synonym_groups(synonyms):
        for phrase in group:
            if phrase not in normalized:
                continue
            for replacement in group:
                expanded = normalize_search_text(normalized.replace(phrase, replacement))
                if expanded and expanded not in variants:
                    variants.append(expanded)
                if len(variants) >= MAX_SEARCH_VARIANTS:
                    break
            if len(variants) >= MAX_SEARCH_VARIANTS:
                break
        if len(variants) >= MAX_SEARCH_VARIANTS:
            break

    return SearchTerms(
        original=original,
        normalized=normalized,
        variants=tuple(variants[:MAX_SEARCH_VARIANTS]),
        tokens=tokens,
    )


def normalize_slug_filter(values: Iterable[str], *, maximum: int = 30) -> list[str]:
    normalized: list[str] = []
    for value in values:
        item = str(value or "").strip().lower()
        if not item:
            continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item):
            raise DiscoveryValidationError("Фильтр содержит недопустимое значение")
        if item not in normalized:
            normalized.append(item)
        if len(normalized) > maximum:
            raise DiscoveryValidationError("Слишком много значений фильтра")
    return normalized


def validate_coordinates(lat: float, lng: float) -> tuple[float, float]:
    try:
        latitude = float(lat)
        longitude = float(lng)
    except (TypeError, ValueError) as exc:
        raise DiscoveryValidationError("Укажите корректные координаты") from exc
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise DiscoveryValidationError("Широта должна быть от -90 до 90")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise DiscoveryValidationError("Долгота должна быть от -180 до 180")
    return latitude, longitude


def validate_nearby_radius(value: int) -> int:
    try:
        radius = int(value)
    except (TypeError, ValueError) as exc:
        raise DiscoveryValidationError("Укажите доступный радиус поиска") from exc
    if radius not in NEARBY_RADII_KM:
        raise DiscoveryValidationError("Радиус должен быть 5, 10, 25, 50 или 100 км")
    return radius


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    latitude, longitude = validate_coordinates(lat, lng)
    lat_delta = radius_km / 111.32
    longitude_scale = max(math.cos(math.radians(latitude)), 0.01)
    lng_delta = radius_km / (111.32 * longitude_scale)
    return (
        max(-180.0, longitude - lng_delta),
        max(-90.0, latitude - lat_delta),
        min(180.0, longitude + lng_delta),
        min(90.0, latitude + lat_delta),
    )


def haversine_km(lat: float, lng: float, other_lat: float, other_lng: float) -> float:
    latitude, longitude = validate_coordinates(lat, lng)
    candidate_lat, candidate_lng = validate_coordinates(other_lat, other_lng)
    radius = 6371.0088
    lat_delta = math.radians(candidate_lat - latitude)
    lng_delta = math.radians(candidate_lng - longitude)
    value = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(latitude))
        * math.cos(math.radians(candidate_lat))
        * math.sin(lng_delta / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


def validate_geojson(
    value: object,
    *,
    max_bytes: int,
    max_coordinates: int,
) -> dict | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise DiscoveryValidationError("GeoJSON должен быть объектом")
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > max_bytes:
        raise DiscoveryValidationError("GeoJSON превышает допустимый размер")
    geometry_type = value.get("type")
    if geometry_type not in {"LineString", "MultiLineString"}:
        raise DiscoveryValidationError("Допустим только маршрут LineString или MultiLineString")
    if set(value).difference({"type", "coordinates"}):
        raise DiscoveryValidationError("GeoJSON содержит неподдерживаемые свойства")

    coordinates = value.get("coordinates")
    lines = [coordinates] if geometry_type == "LineString" else coordinates
    if not isinstance(lines, list) or not lines:
        raise DiscoveryValidationError("Маршрут должен содержать координаты")
    count = 0
    clean_lines: list[list[list[float]]] = []
    for line in lines:
        if not isinstance(line, list) or len(line) < 2:
            raise DiscoveryValidationError("Каждая линия маршрута должна содержать минимум две точки")
        clean_line: list[list[float]] = []
        for coordinate in line:
            if not isinstance(coordinate, list) or len(coordinate) not in {2, 3}:
                raise DiscoveryValidationError("Координата GeoJSON должна содержать longitude и latitude")
            clean_lat, clean_lng = validate_coordinates(coordinate[1], coordinate[0])
            clean_coordinate = [clean_lng, clean_lat]
            if len(coordinate) == 3:
                try:
                    altitude = float(coordinate[2])
                except (TypeError, ValueError) as exc:
                    raise DiscoveryValidationError("Высота GeoJSON должна быть числом") from exc
                if not math.isfinite(altitude):
                    raise DiscoveryValidationError("Высота GeoJSON должна быть конечным числом")
                clean_coordinate.append(altitude)
            clean_line.append(clean_coordinate)
            count += 1
            if count > max_coordinates:
                raise DiscoveryValidationError("Маршрут содержит слишком много координат")
        clean_lines.append(clean_line)
    return {
        "type": geometry_type,
        "coordinates": clean_lines[0] if geometry_type == "LineString" else clean_lines,
    }


def validate_weight_config(
    configured: Mapping[str, int],
    allowed_keys: Iterable[str],
) -> dict[str, int]:
    allowed = set(allowed_keys)
    unknown = set(configured).difference(allowed)
    if unknown:
        raise DiscoveryValidationError(
            f"Неизвестные веса рекомендаций: {', '.join(sorted(unknown))}"
        )
    normalized = {key: int(configured.get(key, 0)) for key in allowed}
    if any(value < 0 or value > 1000 for value in normalized.values()):
        raise DiscoveryValidationError("Вес рекомендации должен быть от 0 до 1000")
    return normalized
