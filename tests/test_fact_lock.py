"""Basic tests for fact-locking and core behavior."""

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
        "free shipping",
        "ethically sourced",
        "fair trade",
        "locally made",
        "nickel-free",
        "nickel free",
        "lead-free",
        "lead free",
        "small-batch",
        "small batch",
        "organic",
        "vegan",
        "certified",
        "made in",
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


def test_supplied_compliance_terms_may_appear_when_sourced():
    g = ListingGenerator(use_llm=False)
    r = g.generate_full_listing(
        product_name="Studio Earrings",
        primary_keyword="studio earrings",
        material="nickel-free brass",
        features=["lead-free", "small-batch"],
        platform="etsy",
    )
    blob = (r["best_title"] + " " + r["description"]).lower()
    assert "nickel-free" in blob
    assert "lead-free" in blob
    assert "small-batch" in blob


def test_negated_claim_is_not_extracted_into_affirmative_tags():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Not Waterproof Pouch",
        primary_keyword="",
        platform="etsy",
    )

    assert "not waterproof" in result["best_title"].lower()
    assert "waterproof" not in result["tags"]
    assert "waterproof pouch" not in result["tags"]
    assert result["meta"]["claim_warnings"] == []


def test_llm_cannot_flip_a_negated_claim_to_affirmative(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["Waterproof Pouch"],
            "best_title": "Waterproof Pouch",
            "description": "DRAFT waterproof pouch",
            "tags": ["waterproof"],
            "meta": {"model": "mock"},
        },
    )

    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Not Waterproof Pouch",
        platform="etsy",
    )

    assert result["meta"]["source"] == "template"
    assert result["meta"]["llm_fact_lock_fallback"] is True
    assert "waterproof" in " ".join(result["meta"]["llm_rejection_reasons"])
    assert "waterproof" not in result["tags"]


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


def test_unsourced_shipping_and_handmade_claims_force_fallback(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["Handmade Cup"],
            "best_title": "Handmade Cup",
            "description": "DRAFT cup with free shipping",
            "tags": ["handmade"],
            "meta": {"model": "mock"},
        },
    )
    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Cup", primary_keyword="cup", platform="etsy"
    )
    output = (
        result["best_title"] + " " + result["description"] + " " + " ".join(result["tags"])
    ).lower()
    assert "handmade" not in output
    assert "free shipping" not in output
    assert result["meta"]["source"] == "template"


def test_unsourced_numbers_and_vocabulary_force_fallback(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["Cup"],
            "best_title": "Cup",
            "description": "DRAFT cup weighs 12 ounces and is ceramic",
            "tags": ["cup"],
            "meta": {"model": "mock"},
        },
    )
    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Cup", primary_keyword="cup", platform="etsy"
    )
    assert result["meta"]["source"] == "template"
    reasons = " ".join(result["meta"]["llm_rejection_reasons"])
    assert "unsourced" in reasons


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
