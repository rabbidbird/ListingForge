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


def test_copyable_description_contains_only_buyer_facing_product_content():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon Pendant",
        item_noun="necklace",
        material="sterling silver",
        platform="etsy",
    )

    description = result["description"].lower()
    for internal_phrase in ("draft", "sellerdrafts", "you supplied", "verify", "human review"):
        assert internal_phrase not in description
    assert "material: sterling silver" in description
    assert "DRAFT" in result["disclaimer"]
    assert result["review_notes"]
    assert result["missing_fact_prompts"]


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


def test_blank_material_does_not_create_a_metal_claim():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon pendant necklace",
        item_noun="necklace",
        material="",
        platform="etsy",
    )

    output = f"{result['best_title']} {result['description']}".lower()
    for metal in ("sterling", "silver", "gold", "brass"):
        assert metal not in output


def test_occasion_is_a_tag_and_description_fact_but_not_a_title_descriptor():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon pendant necklace",
        item_noun="necklace",
        color="blue",
        material="glass",
        occasion_or_recipient="birthday gift",
        platform="etsy",
    )

    assert "birthday" not in result["best_title"].lower()
    assert "gift" not in result["best_title"].lower()
    assert "birthday gift" in result["tags"]
    assert "birthday gift" in result["description"].lower()


def test_short_etsy_inputs_produce_a_noun_led_title_under_fifteen_words():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Celestial moon",
        item_noun="pendant necklace",
        color="blue",
        material="glass",
        size="18 inch",
        features=["adjustable chain"],
        platform="etsy",
    )

    title_words = result["best_title"].split()
    assert result["best_title"].lower().startswith("pendant necklace")
    assert len(title_words) < 15
    assert len({word.casefold() for word in title_words}) == len(title_words)
    assert "adjustable" not in result["best_title"].lower()
    assert "adjustable chain" in result["tags"]


def test_item_noun_already_in_product_name_keeps_the_supplied_phrase_order():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Teardrop pendant necklace",
        item_noun="necklace",
        primary_keyword="teardrop pendant necklace",
        color="blue",
        material="stainless steel",
        size="18 inch",
        platform="etsy",
    )

    assert result["best_title"].startswith("Teardrop Pendant Necklace")
    assert not result["best_title"].startswith("Necklace Teardrop")
    assert result["scores"]["title"]["score"] >= 90


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


def test_llm_may_only_order_complete_source_phrase_ids(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "title_phrase_ids": [["keyword", "material"], ["product"]],
            "tag_phrase_ids": ["keyword", "material"],
            "description_feature_ids": ["feature_2", "feature_1"],
            "meta": {"model": "mock"},
        },
    )

    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Studio Cup",
        primary_keyword="ceramic studio cup",
        material="white stoneware",
        features=["Height: 4 inches", "Weight: 12 ounces"],
        platform="etsy",
    )

    assert result["meta"]["source"] == "llm"
    assert result["best_title"] == "ceramic studio cup | white stoneware"
    assert result["tags"] == ["ceramic studio cup", "white stoneware"]
    assert result["description"].index("Weight: 12 ounces") < result["description"].index(
        "Height: 4 inches"
    )


def test_free_form_llm_cannot_reassociate_supplied_numbers(monkeypatch):
    monkeypatch.setattr("core.generator.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "core.generator.generate_with_llm",
        lambda **_: {
            "titles": ["Weight 10 In"],
            "best_title": "Weight 10 In",
            "description": "DRAFT weight 10 in length 2 lb",
            "tags": ["weight", "length"],
            "meta": {"model": "mock"},
        },
    )

    result = ListingGenerator(use_llm=True).generate_full_listing(
        product_name="Parcel",
        features=["Weight 2 lb", "Length 10 in"],
        platform="etsy",
    )

    assert result["meta"]["source"] == "template"
    assert result["meta"]["llm_fact_lock_fallback"] is True
    assert "free-form LLM output is not accepted" in " ".join(
        result["meta"]["llm_rejection_reasons"]
    )
    assert "Weight 10 In" not in result["best_title"]


def test_negated_unlisted_attribute_is_not_extracted_into_tags():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Not Washable Scarf",
        platform="etsy",
    )

    assert result["tags"] == ["not washable scarf"]
    assert "washable" not in result["tags"]
    assert "washable scarf" not in result["tags"]


def test_overlong_source_title_uses_neutral_draft_label_instead_of_truncation():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="x" * 141,
        platform="etsy",
    )

    assert result["best_title"] == "DRAFT Product Listing"
    assert len(result["best_title"]) <= 140


def test_source_measurement_signs_and_mixed_numbers_are_not_cosmetically_rewritten():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="-5 Degree Panel 1 1/2 Inch",
        platform="etsy",
    )

    assert "-5 Degree" in result["best_title"]
    assert "1 1/2 Inch" in result["best_title"]
    assert "-5 degree" in result["tags"]
    assert "1 1/2 inch" in result["tags"]


def test_alphanumeric_identifier_casing_is_preserved_in_template_titles():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Model x100 Reader",
        platform="etsy",
    )

    assert "x100" in result["best_title"]
    assert "X100" not in result["best_title"]


def test_description_is_structured_and_preserves_complete_supplied_relationships():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Model x100 wall panel.",
        item_noun="wall panel",
        features=["Length: 10 in; weight: 2 lb.", "Not suitable for outdoor use"],
        platform="etsy",
    )

    description = result["description"]
    assert description.startswith("About this item\n\nModel x100 wall panel.")
    assert "Product details" in description
    assert "• Length: 10 in; weight: 2 lb." in description
    assert "• Not suitable for outdoor use" in description
    assert ".." not in description


def test_etsy_title_keeps_a_supplied_primary_phrase_contiguous_when_it_fits():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Teardrop pendant necklace",
        primary_keyword="pressed flower necklace",
        item_noun="pendant necklace",
        material="stainless steel chain",
        platform="etsy",
    )

    assert "pressed flower necklace" in result["best_title"].casefold()
    assert not any(
        "primary phrase is absent" in item.casefold()
        for item in result["scores"]["title"]["feedback"]
    )


def test_overlong_etsy_phrases_use_only_contiguous_supplied_subphrases():
    phrase = "birthday gift for flower lover"
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Pendant",
        extra_keywords=[phrase],
        platform="etsy",
    )

    phrase_words = phrase.split()
    allowed = {
        " ".join(phrase_words[start:end])
        for start in range(len(phrase_words))
        for end in range(start + 2, len(phrase_words) + 1)
        if len(" ".join(phrase_words[start:end])) <= 20
    }
    derived = [tag for tag in result["tags"] if tag != "pendant"]
    assert derived
    assert set(derived) <= allowed
    assert all(len(tag) <= 20 for tag in derived)
    assert "birthday gift for" not in derived
    assert "birthday gift" in derived
    assert "flower lover" in derived


def test_etsy_title_uses_a_readable_descriptor_word_budget_and_minor_word_casing():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Celestial moon pendant necklace",
        primary_keyword="moon pendant necklace",
        item_noun="pendant necklace",
        color="deep blue",
        material="sterling silver and glass",
        size="18 inch chain",
        platform="etsy",
    )

    assert len(result["best_title"].split()) <= 12
    assert "Silver and Glass" in result["best_title"]
    assert "Silver And Glass" not in result["best_title"]


def test_overlong_gift_phrase_produces_readable_contiguous_tags():
    phrase = "birthday gift for her"
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Pendant",
        occasion_or_recipient=phrase,
        platform="etsy",
    )

    assert "birthday gift" in result["tags"]
    assert "gift for her" in result["tags"]
    assert "birthday gift for" not in result["tags"]


def test_overlong_negated_phrase_is_never_split_into_affirmative_tags():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Pouch",
        extra_keywords=["not waterproof for outdoor use"],
        platform="etsy",
    )

    assert all("waterproof" not in tag for tag in result["tags"])


def test_digital_product_prompts_ask_about_files_not_physical_attributes():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Budget planner download",
        category="digital",
        platform="etsy",
    )

    prompts = " ".join(result["missing_fact_prompts"]).casefold()
    assert "file" in prompts
    assert "material" not in prompts
    assert "size" not in prompts
    assert "physical" not in prompts


def test_fewer_accurate_etsy_tags_can_have_a_clean_status():
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Blue mug",
        primary_keyword="blue mug",
        platform="etsy",
    )

    assert len(result["tags"]) < 13
    assert result["scores"]["tags"]["status"] == "Pass"
