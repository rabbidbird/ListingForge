from __future__ import annotations

from core.auth import authenticate_user, create_user_session, get_user_by_session_token
from core.database import session_scope
from core.generation_service import generate_for_user
from core.generator import ListingGenerator
from core.usage import get_usage
from core.utils import delete_listing, get_history, get_listing_by_id, save_listing, update_listing


def test_signup_login_and_opaque_session(user_factory):
    user = user_factory(email="Owner@Example.com")
    with session_scope() as session:
        authenticated = authenticate_user(
            session,
            email="owner@example.com",
            password="correct horse battery staple",
        )
        assert authenticated is not None
        token = create_user_session(session, authenticated.id)
    assert token and "owner@example.com" not in token
    with session_scope() as session:
        assert get_user_by_session_token(session, token).id == user.id
        assert (
            authenticate_user(session, email="owner@example.com", password="wrong password") is None
        )


def test_user_cannot_read_update_or_delete_another_users_listing(user_factory):
    owner = user_factory(email="owner@example.com")
    stranger = user_factory(email="stranger@example.com")
    result = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Blue Mug", primary_keyword="blue mug", platform="etsy"
    )
    listing_id = save_listing(owner.id, result)

    assert get_listing_by_id(owner.id, listing_id) is not None
    assert get_listing_by_id(stranger.id, listing_id) is None
    assert get_history(stranger.id) == []
    assert update_listing(stranger.id, listing_id, result) is False
    assert delete_listing(stranger.id, listing_id) is False
    assert get_listing_by_id(owner.id, listing_id) is not None


def test_authenticated_generation_path_saves_private_draft_and_usage(user_factory):
    user = user_factory()
    result, listing_id = generate_for_user(
        user.id,
        {
            "product_name": "Plain Cup",
            "primary_keyword": "plain cup",
            "platform": "etsy",
            "force_template": True,
        },
    )
    assert result["meta"]["is_draft"] is True
    assert get_listing_by_id(user.id, listing_id)["best_title"] == result["best_title"]
    assert get_usage(user.id)["daily"] == 1
