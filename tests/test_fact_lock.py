"""Basic tests for fact-locking and core behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generator import ListingGenerator


def test_no_invention_on_minimal_input():
    g = ListingGenerator(use_llm=False)
    r = g.generate_full_listing(
        product_name="women's necklace",
        primary_keyword="necklace",
        category="jewelry",
        platform="etsy",
    )
    text = (r["best_title"] + " " + r["description"] + " " + " ".join(r["tags"])).lower()
    forbidden = [
        "sterling",
        "handmade",
        "bestseller",
        "hypoallergenic",
        "limited stock",
        "ships fast",
    ]
    for term in forbidden:
        assert term not in text, f"Invented claim found: {term}"
    assert r["meta"]["is_draft"] is True
    assert "DRAFT" in r["disclaimer"]


def test_supplied_facts_appear():
    g = ListingGenerator(use_llm=False)
    r = g.generate_full_listing(
        product_name="Moon Pendant",
        primary_keyword="moon pendant necklace",
        material="sterling silver",
        audience="women",
        features=["Hypoallergenic", "Adjustable chain"],
        platform="etsy",
    )
    assert (
        "sterling silver" in r["best_title"].lower()
        or "sterling silver" in r["description"].lower()
    )
    assert r["meta"]["claim_warnings"] == []


def test_tags_respect_etsy_limit():
    g = ListingGenerator(use_llm=False)
    r = g.generate_full_listing(
        product_name="Test Product",
        primary_keyword="test product",
        platform="etsy",
    )
    assert len(r["tags"]) <= 13
    for t in r["tags"]:
        assert len(t) <= 20


def test_unsourced_llm_claim_forces_template_fallback(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["Sterling Silver Cup"],
            "best_title": "Sterling Silver Cup",
            "description": "DRAFT sterling silver cup",
            "tags": ["sterling silver"],
            "meta": {"model": "mock"},
        },
    )
    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Cup", primary_keyword="cup", platform="etsy"
    )
    output = (
        result["best_title"] + " " + result["description"] + " " + " ".join(result["tags"])
    ).lower()
    assert "sterling" not in output
    assert result["meta"]["source"] == "template"
    assert result["meta"]["llm_fact_lock_fallback"] is True


def test_overlong_llm_title_option_forces_template_fallback(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["cup " * 40],
            "best_title": "Cup",
            "description": "DRAFT cup supplied by user for review before publishing",
            "tags": ["cup"],
            "meta": {"model": "mock"},
        },
    )
    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Cup", primary_keyword="cup", platform="etsy"
    )
    assert result["meta"]["source"] == "template"
    assert "title exceeds platform limit" in result["meta"]["llm_rejection_reasons"]


if __name__ == "__main__":
    test_no_invention_on_minimal_input()
    test_supplied_facts_appear()
    test_tags_respect_etsy_limit()
    print("All fact-lock tests passed")
