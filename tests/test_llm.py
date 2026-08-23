"""Contract tests for the optional phrase-selection provider boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import core.llm


def _fake_client(content: str, captured: dict):
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_provider_response_exposes_only_phrase_plan_fields(monkeypatch):
    captured: dict = {}
    payload = {
        "title_phrase_ids": [["product", "material"]],
        "tag_phrase_ids": ["keyword"],
        "description_feature_ids": ["feature_1"],
        # Even if a provider disregards the schema and adds prose, it is discarded.
        "best_title": "Invented publishable claim",
    }
    monkeypatch.setattr(core.llm, "is_llm_available", lambda: True)
    monkeypatch.setattr(
        core.llm,
        "get_client",
        lambda: _fake_client(json.dumps(payload), captured),
    )

    result = core.llm.generate_with_llm(
        product_name="Studio Mug",
        primary_keyword="coffee mug",
        material="white stoneware",
        features=["Height: 4 inches"],
    )

    assert result == {
        "title_phrase_ids": [["product", "material"]],
        "tag_phrase_ids": ["keyword"],
        "description_feature_ids": ["feature_1"],
        "meta": {"source": "llm", "model": "gpt-4o-mini"},
    }
    assert captured["response_format"] == {"type": "json_object"}
    prompt = captured["messages"][1]["content"]
    assert '"id": "feature_1"' in prompt
    assert '"text": "Height: 4 inches"' in prompt


def test_provider_response_with_wrong_plan_types_falls_back(monkeypatch):
    monkeypatch.setattr(core.llm, "is_llm_available", lambda: True)
    monkeypatch.setattr(
        core.llm,
        "get_client",
        lambda: _fake_client(
            json.dumps(
                {
                    "title_phrase_ids": [["product"]],
                    "tag_phrase_ids": "product",
                    "description_feature_ids": [],
                }
            ),
            {},
        ),
    )

    assert core.llm.generate_with_llm(product_name="Studio Mug") is None


def test_provider_exception_falls_back_without_returning_partial_text(monkeypatch):
    def fail(**_kwargs):
        raise TimeoutError("provider timeout")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    monkeypatch.setattr(core.llm, "is_llm_available", lambda: True)
    monkeypatch.setattr(core.llm, "get_client", lambda: client)

    assert core.llm.generate_with_llm(product_name="Studio Mug") is None
