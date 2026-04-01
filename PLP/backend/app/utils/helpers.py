from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_candidate_code() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"CAND-{timestamp}-{suffix}"


def sanitize_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return normalized or "audio"


def slugify_text(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized or "module"


def trim_text(value: str | None, fallback: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def basename_from_path(value: str) -> str:
    return Path(str(value or "")).name


def serialize_text_list(items: list[str] | str | None) -> str:
    if items is None:
        return "[]"
    if isinstance(items, str):
        stripped = items.strip()
        return stripped if stripped else "[]"
    return json.dumps([str(item).strip() for item in items if str(item).strip()], ensure_ascii=False)


def deserialize_text_list(value: str | None) -> list[str]:
    if not value:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return [line.strip("- ").strip() for line in stripped.splitlines() if line.strip()]
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    if isinstance(payload, str):
        return [payload.strip()] if payload.strip() else []
    return []


def extract_json_object(content: str) -> dict:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return json.loads(content)

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))
