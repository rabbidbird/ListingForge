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
    forbidden = ["sterling", "handmade", "bestseller", "hypoallergenic", "limited stock", "ships fast"]
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
    assert "sterling silver" in r["best_title"].lower() or "sterling silver" in r["description"].lower()
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


if __name__ == "__main__":
    test_no_invention_on_minimal_input()
    test_supplied_facts_appear()
    test_tags_respect_etsy_limit()
    print("All fact-lock tests passed")
