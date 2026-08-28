from __future__ import annotations

import pandas as pd
import pytest

from core.csv_processor import CSVValidationError, read_csv_bytes, validate_csv_rows
from core.generator import ListingGenerator
from core.utils import export_to_dataframe


def test_empty_csv_is_rejected_cleanly():
    with pytest.raises(CSVValidationError, match="empty"):
        read_csv_bytes(b"")
    with pytest.raises(CSVValidationError, match="empty"):
        read_csv_bytes(b"\n\n")


def test_nan_values_are_cleaned_and_bad_rows_do_not_abort_job():
    frame = pd.DataFrame(
        [
            {"product_name": float("nan"), "material": float("nan")},
            {
                "product_name": "Plain Cup",
                "primary_keyword": float("nan"),
                "material": float("nan"),
                "features": float("nan"),
                "platform": "etsy",
            },
        ]
    )
    rows = validate_csv_rows(frame)
    assert rows[0].error == "Product name is required."
    assert rows[1].error is None
    assert rows[1].payload["material"] == ""
    result = ListingGenerator(use_llm=False).generate_full_listing(**rows[1].payload)
    combined = str(result).lower()
    assert "nan" not in combined


def test_csv_export_neutralizes_spreadsheet_formula_prefixes():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="=HYPERLINK malicious label",
        primary_keyword="@SUM formula-looking keyword",
        platform="etsy",
    )

    row = export_to_dataframe([result]).iloc[0]
    assert row["Product Name"].startswith("'=")
    assert row["Primary Keyword"].startswith("'@")
    assert row["Best Title"].startswith("'=")


def test_csv_preserves_single_draft_optional_fact_fields():
    frame = read_csv_bytes(
        b"product_name,item_noun,color,size,occasion_or_recipient,platform\n"
        b"Moon Pendant,necklace,blue,18 inch,birthday gift,etsy\n"
    )

    row = validate_csv_rows(frame)[0]

    assert row.error is None
    assert row.payload is not None
    assert row.payload["item_noun"] == "necklace"
    assert row.payload["color"] == "blue"
    assert row.payload["size"] == "18 inch"
    assert row.payload["occasion_or_recipient"] == "birthday gift"


def test_export_shows_statuses_not_numeric_scores_or_grades():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon Pendant", platform="etsy"
    )

    row = export_to_dataframe([result]).iloc[0]

    assert "Checklist Status" in row.index
    assert "Overall Score" not in row.index
    assert "Grade" not in row.index
    assert "Draft Disclaimer" in row.index
