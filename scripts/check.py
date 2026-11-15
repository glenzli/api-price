#!/usr/bin/env python3
"""Validate api-price and generate its release manifest."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import urlparse


ROOT_KEYS = {"schema", "catalog_version", "updated_at", "currency", "unit", "references", "prices"}
REFERENCE_KEYS = {"id", "url", "checked_at"}
PRICE_KEYS = {
    "scope", "model", "reference", "valid_from", "valid_until", "input_per_million",
    "cached_input_per_million", "cache_write_per_million", "output_per_million", "note",
    "request_input_min", "request_input_max", "rate_tier",
}
REQUIRED_PRICE_KEYS = {
    "scope", "model", "reference", "valid_from", "input_per_million",
    "output_per_million",
}
CLIENT_SCOPES = {"codex", "antigravity", "claude-code"}
PROVIDER_SCOPES = {"openai", "google", "anthropic", "deepseek", "qwen", "zai", "kimi", "minimax", "xai", "mistral", "cohere"}
RATE_TIERS = {"standard", "priority", "fast", "ultrafast", "batch", "flex", "peak", "off-peak", "standard-short-context", "standard-long-context", "priority-short-context", "priority-long-context"}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z")
VERSION_RE = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[1-9][0-9]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_CATALOG_BYTES = 512 * 1024
MANIFEST_SCHEMA = "api-price-manifest/v1"


def fail(message: str) -> None:
    raise ValueError(message)


def exact_keys(value: dict[str, object], allowed: set[str], *, required: set[str] | None = None, where: str) -> None:
    unknown = set(value) - allowed
    missing = (required or allowed) - set(value)
    if unknown:
        fail(f"{where} has unknown keys: {', '.join(sorted(unknown))}")
    if missing:
        fail(f"{where} is missing keys: {', '.join(sorted(missing))}")


def text(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 500:
        fail(f"{where} must be a non-empty bounded string")
    return value


def day(value: object, *, where: str) -> date:
    try:
        return date.fromisoformat(text(value, where=where))
    except ValueError as exc:
        fail(f"{where} must be an ISO date: {exc}")


def rate(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{where} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 <= parsed <= 10_000:
        fail(f"{where} is outside the allowed range")
    return parsed


def load_catalog(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_CATALOG_BYTES:
        fail("catalog size is invalid")
    document = tomllib.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        fail("catalog root must be a table")
    exact_keys(document, ROOT_KEYS, where="catalog")
    if document["schema"] != "api-price/v1":
        fail("unsupported catalog schema")
    version = text(document["catalog_version"], where="catalog_version")
    if not VERSION_RE.fullmatch(version):
        fail("catalog_version must use YYYY.MM.DD.N")
    try:
        datetime.fromisoformat(text(document["updated_at"], where="updated_at"))
    except ValueError as exc:
        fail(f"updated_at must be an ISO timestamp: {exc}")
    if document["currency"] != "USD" or document["unit"] != "per_million_tokens":
        fail("catalog supports only USD per-million-token rates")

    references = document["references"]
    if not isinstance(references, list) or not references:
        fail("references must be a non-empty array")
    reference_ids: set[str] = set()
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            fail(f"references[{index}] must be a table")
        exact_keys(reference, REFERENCE_KEYS, where=f"references[{index}]")
        identifier = text(reference["id"], where=f"references[{index}].id")
        if not ID_RE.fullmatch(identifier) or identifier in reference_ids:
            fail(f"references[{index}].id is invalid or duplicated")
        parsed = urlparse(text(reference["url"], where=f"references[{index}].url"))
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            fail(f"references[{index}].url must be public HTTPS")
        day(reference["checked_at"], where=f"references[{index}].checked_at")
        reference_ids.add(identifier)

    prices = document["prices"]
    if not isinstance(prices, list) or not prices:
        fail("prices must be a non-empty array")
    ranges: dict[tuple[str, str], list[tuple[date, date | None, int | None, int | None, str]]] = {}
    for index, price in enumerate(prices):
        if not isinstance(price, dict):
            fail(f"prices[{index}] must be a table")
        exact_keys(price, PRICE_KEYS, required=REQUIRED_PRICE_KEYS, where=f"prices[{index}]")
        scope = text(price["scope"], where=f"prices[{index}].scope")
        model = text(price["model"], where=f"prices[{index}].model")
        reference = text(price["reference"], where=f"prices[{index}].reference")
        if scope not in CLIENT_SCOPES | PROVIDER_SCOPES or not ID_RE.fullmatch(model):
            fail(f"prices[{index}] has an unsupported scope or model")
        if scope in CLIENT_SCOPES and "cached_input_per_million" not in price:
            fail(f"prices[{index}] requires the client cache-read reference")
        if reference not in reference_ids:
            fail(f"prices[{index}] uses an unknown reference")
        start = day(price["valid_from"], where=f"prices[{index}].valid_from")
        end = day(price["valid_until"], where=f"prices[{index}].valid_until") if "valid_until" in price else None
        if end is not None and end < start:
            fail(f"prices[{index}] has an inverted date range")
        for field in ("input_per_million", "output_per_million"):
            rate(price[field], where=f"prices[{index}].{field}")
        if "cached_input_per_million" in price:
            rate(price["cached_input_per_million"], where=f"prices[{index}].cached_input_per_million")
        if "cache_write_per_million" in price:
            rate(price["cache_write_per_million"], where=f"prices[{index}].cache_write_per_million")
        if "note" in price:
            text(price["note"], where=f"prices[{index}].note")
        lower, upper = price.get("request_input_min"), price.get("request_input_max")
        if any(value is not None and (type(value) is not int or not 0 <= value <= 2**53 - 1) for value in (lower, upper)):
            fail(f"prices[{index}] has invalid request-input bounds")
        if lower is not None and upper is not None and upper < lower:
            fail(f"prices[{index}] has inverted request-input bounds")
        tier = price.get("rate_tier", "standard")
        if not isinstance(tier, str) or tier not in RATE_TIERS:
            fail(f"prices[{index}] has an unsupported rate tier")
        ranges.setdefault((scope, model), []).append((start, end, lower, upper, tier))

    for key, periods in ranges.items():
        for index, previous in enumerate(periods):
            for current in periods[index + 1:]:
                dates_overlap = max(previous[0], current[0]) <= min(previous[1] or date.max, current[1] or date.max)
                inputs_overlap = max(previous[2] or 0, current[2] or 0) <= min(
                    previous[3] if previous[3] is not None else 2**53 - 1,
                    current[3] if current[3] is not None else 2**53 - 1)
                if previous[4] == current[4] and dates_overlap and inputs_overlap:
                    fail(f"overlapping date ranges and input tiers for {key[0]}:{key[1]}")
    return document, raw


def expected_manifest(document: dict[str, object], raw: bytes) -> dict[str, object]:
    return {
        "schema": MANIFEST_SCHEMA,
        "catalog_schema": document["schema"],
        "catalog_version": document["catalog_version"],
        "asset": "api-price.toml",
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def validate_manifest(path: Path, expected: dict[str, object]) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        fail("manifest root must be an object")
    exact_keys(manifest, set(expected), where="manifest")
    if manifest != expected or not SHA256_RE.fullmatch(str(manifest.get("sha256", ""))):
        fail("manifest does not match api-price.toml")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("api-price.toml"))
    parser.add_argument("--manifest", type=Path, default=Path("api-price.manifest.json"))
    parser.add_argument("--write-manifest", type=Path)
    args = parser.parse_args()
    try:
        document, raw = load_catalog(args.catalog)
        expected = expected_manifest(document, raw)
        if args.write_manifest:
            args.write_manifest.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        validate_manifest(args.manifest, expected)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"api-price validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"api-price {document['catalog_version']} ok ({len(document['prices'])} price periods, {expected['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
