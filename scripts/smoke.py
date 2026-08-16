"""Basic import, schema, generator, and health smoke used by CI."""

from __future__ import annotations

from core.generator import ListingGenerator
from core.models import Base
from core.web import app, healthz


def main() -> None:
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Smoke Test Cup", primary_keyword="test cup", platform="etsy"
    )
    assert result["meta"]["is_draft"] is True
    assert result["meta"]["claim_warnings"] == []
    assert "DRAFT" in result["disclaimer"]
    assert app.title == "TrueDraft edge"
    assert {"users", "listings", "usage_events", "subscriptions"}.issubset(Base.metadata.tables)
    assert healthz() == {"status": "ok"}
    print("TrueDraft smoke check passed")


if __name__ == "__main__":
    main()
