"""Regression coverage for fact preservation across draft lifecycle boundaries."""

from __future__ import annotations

import pandas as pd

from core.csv_processor import validate_csv_rows
from core.draft_review import draft_export_ready, recheck_edited_draft
from core.generator import ListingGenerator
from core.utils import export_to_dataframe, get_listing_by_id, save_listing


def test_overlong_mandatory_product_requires_a_shorter_title_not_optional_descriptors():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Very detailed verified product description " * 5,
        material="stainless steel",
        color="blue",
        platform="etsy",
    )
    assert result["best_title"] == "DRAFT Product Listing"
    assert result["scores"]["title"]["status"] != "Pass"
    assert not draft_export_ready(result)
    checked = recheck_edited_draft(
        result,
        title="",
        description=result["description"],
        tags=result["tags"],
        explicitly_verified=True,
    )
    assert not draft_export_ready(checked)


def test_generation_keeps_repeated_dimension_tokens_and_negation_scope():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="5 x 5 inch print",
        features=[
            "10 x 20 x 10 cm box",
            "20 cm chain with 10 cm extension",
            "1.25 inch pendant; not handmade necklace and not silver",
        ],
        platform="etsy",
    )

    title = result["best_title"].casefold()
    description = result["description"].casefold()
    assert "5 x 5 inch print" in title
    assert "10 x 20 x 10 cm box" in description
    assert "20 cm chain with 10 cm extension" in description
    assert "1.25 inch pendant; not handmade necklace and not silver" in description


def test_csv_generation_preserves_decimal_units_and_paired_dimensions():
    row = validate_csv_rows(
        pd.DataFrame(
            [
                {
                    "product_name": "10 x 20 x 10 cm box",
                    "features": "1.25 inch pendant|20 cm chain with 10 cm extension",
                    "platform": "etsy",
                }
            ]
        )
    )[0]

    assert row.error is None
    result = ListingGenerator(use_llm=False).generate_full_listing(**row.payload)
    assert "10 x 20 x 10 cm box" in result["best_title"].casefold()
    assert "1.25 inch pendant" in result["description"].casefold()
    assert "20 cm chain with 10 cm extension" in result["description"].casefold()


def test_save_reload_edit_and_export_keep_complete_factual_spans(user_factory):
    user = user_factory(email="repair-facts@example.com")
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="5 x 5 inch print",
        features=["20 cm chain with 10 cm extension", "not silver"],
        platform="etsy",
    )
    listing_id = save_listing(user.id, original)
    loaded = get_listing_by_id(user.id, listing_id)
    assert loaded is not None

    checked = recheck_edited_draft(
        loaded,
        title=loaded["best_title"],
        description=loaded["description"],
        tags=loaded["tags"],
        explicitly_verified=False,
    )
    assert draft_export_ready(checked) is True
    exported = export_to_dataframe([checked]).iloc[0]
    assert "5 x 5 inch print" in exported["Best Title"].casefold()
    assert "20 cm chain with 10 cm extension" in exported["Description"].casefold()
    assert "not silver" in exported["Description"].casefold()


def test_invalid_etsy_tag_is_visible_in_generation_editor_and_export():
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Pendant",
        extra_keywords=["pendant: 1.25 in"],
        platform="etsy",
    )

    assert "pendant: 1.25 in" in original["tags"]
    assert original["scores"]["tags"]["status"] == "Verify"
    assert original["scores"]["overall"]["status"] == "Verify"
    assert any("unsupported characters" in note for note in original["review_notes"])
    assert draft_export_ready(original) is False

    checked = recheck_edited_draft(
        original,
        title=original["best_title"],
        description=original["description"],
        tags=original["tags"],
        explicitly_verified=True,
    )
    assert checked["scores"]["tags"]["status"] == "Verify"
    assert checked["edit_review"]["export_ready"] is False
    # The export boundary retains review rows and their current validation state.
    exported = export_to_dataframe([checked]).iloc[0]
    assert exported["Tags Status"] == "Verify"
    assert "unsupported characters" in exported["Review Notes"]


def test_edit_review_detects_per_field_damage_to_repeated_numbers_associations_and_negation():
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="5 x 5 inch print",
        features=["20 cm chain with 10 cm extension", "1.25 inch pendant", "not silver"],
        platform="shopify",
    )

    checked = recheck_edited_draft(
        original,
        title="5 x inch print",
        description=original["description"]
        .replace("20 cm chain with 10 cm extension", "10 cm chain with 20 cm extension")
        .replace("1.25 inch pendant", "1.5 inch pendant")
        .replace("not silver", "silver"),
        tags=[tag.replace("5 x 5 inch print", "5 x inch print") for tag in original["tags"]],
        explicitly_verified=False,
    )

    warnings = checked["edit_review"]["warnings"]
    changed = {(warning["phrase"], warning["kind"]) for warning in warnings}
    assert ("5 x 5 inch print", "fact_span") in changed
    assert ("20 cm chain with 10 cm extension", "fact_span") in changed
    assert ("1.25 inch pendant", "fact_span") in changed
    assert ("not silver", "fact_span") in changed
    assert any(
        warning["kind"] == "fact_span" and "in the tags" in warning["message"]
        for warning in warnings
    )
    assert draft_export_ready(checked) is False

    explicitly_verified = recheck_edited_draft(
        checked,
        title=checked["best_title"],
        description=checked["description"],
        tags=checked["tags"],
        explicitly_verified=True,
    )
    assert draft_export_ready(explicitly_verified) is True


def test_shopify_title_target_is_review_feedback_not_a_hard_export_lock():
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Plain cup", platform="shopify"
    )
    checked = recheck_edited_draft(
        original,
        title="x" * 71,
        description=original["description"],
        tags=original["tags"],
        explicitly_verified=True,
    )

    assert checked["scores"]["title"]["status"] == "Review"
    assert not any(
        warning["kind"] == "platform_validation" and warning["phrase"] == "title"
        for warning in checked["edit_review"]["warnings"]
    )
    assert draft_export_ready(checked) is True


def test_legacy_partial_numeric_product_title_requires_review_but_honors_explicit_verification():
    legacy = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="5 x 5 inch print", platform="shopify"
    )
    legacy["best_title"] = "5 X Inch Print"
    legacy["titles"] = [legacy["best_title"]]
    legacy["meta"].pop("source_rendered_fields", None)

    reviewed = recheck_edited_draft(
        legacy,
        title=legacy["best_title"],
        description=legacy["description"],
        tags=legacy["tags"],
        explicitly_verified=False,
    )
    assert any(
        warning["category"] == "Legacy source fact changed"
        for warning in reviewed["edit_review"]["warnings"]
    )
    assert draft_export_ready(reviewed) is False

    verified = recheck_edited_draft(
        legacy,
        title=legacy["best_title"],
        description=legacy["description"],
        tags=legacy["tags"],
        explicitly_verified=True,
    )
    assert draft_export_ready(verified) is True
