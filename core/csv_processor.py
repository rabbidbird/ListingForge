"""Safe CSV parsing that isolates row-level validation failures."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from .config import get_settings
from .generation_service import GenerationInputError, normalize_generation_input
from .utils import clean_optional_text


class CSVValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedCSVRow:
    row_number: int
    payload: dict[str, Any] | None
    error: str | None


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    if not content or not content.strip():
        raise CSVValidationError("The CSV file is empty.")
    if len(content) > get_settings().max_upload_bytes:
        max_mb = get_settings().max_upload_bytes / 1_000_000
        raise CSVValidationError(f"CSV exceeds the {max_mb:g} MB upload limit.")
    try:
        frame = pd.read_csv(BytesIO(content), dtype=object)
    except pd.errors.EmptyDataError as exc:
        raise CSVValidationError("The CSV file is empty.") from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise CSVValidationError("The file is not a valid UTF-8 CSV.") from exc
    frame.columns = [clean_optional_text(column).lower() for column in frame.columns]
    if "product_name" not in frame.columns:
        raise CSVValidationError("CSV must contain a product_name column.")
    return frame


def validate_csv_rows(frame: pd.DataFrame, *, limit: int | None = None) -> list[ValidatedCSVRow]:
    rows: list[ValidatedCSVRow] = []
    selected = frame if limit is None else frame.head(limit)
    for position, (_, row) in enumerate(selected.iterrows(), start=2):
        category = clean_optional_text(row.get("category")) or "default"
        platform = clean_optional_text(row.get("platform")) or "etsy"
        features = clean_optional_text(row.get("features"))
        extra_keywords = clean_optional_text(row.get("extra_keywords"))
        data = {
            "product_name": row.get("product_name"),
            "primary_keyword": row.get("primary_keyword"),
            "category": category,
            "material": row.get("material"),
            "audience": row.get("audience"),
            "features": features.split("|") if features else [],
            "extra_keywords": extra_keywords.split(",") if extra_keywords else [],
            "platform": platform,
        }
        try:
            rows.append(ValidatedCSVRow(position, normalize_generation_input(data), None))
        except GenerationInputError as exc:
            rows.append(ValidatedCSVRow(position, None, str(exc)))
    return rows
