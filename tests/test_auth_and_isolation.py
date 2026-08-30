from __future__ import annotations

from datetime import timedelta

import pytest

import core.auth
from core.auth import (
    AuthError,
    authenticate_user,
    create_user_session,
    find_user_by_google_subject,
    get_or_create_google_user,
    get_user_by_session_token,
    link_google_identity,
    register_user,
    revoke_user_session,
)
from core.database import session_scope
from core.generation_service import generate_for_user
from core.generator import ListingGenerator
from core.models import User, UserSession, utcnow
from core.usage import UsageLimitError, get_usage, reserve_generation
from core.utils import (
    delete_listing,
    get_full_history,
    get_history,
    get_listing_by_id,
    save_listing,
    update_listing,
)


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


def test_login_bounds_oversized_credentials_before_argon2(user_factory, monkeypatch):
    user = user_factory(email="bounded@example.com")
    candidates: list[str] = []

    def record_verify(_password_hash: str, candidate: str) -> bool:
        candidates.append(candidate)
        return False

    monkeypatch.setattr(core.auth, "verify_password", record_verify)
    with session_scope() as session:
        assert (
            authenticate_user(
                session,
                email=user.email,
                password="x" * 10_000,
            )
            is None
        )
        assert authenticate_user(session, email="x" * 10_000, password="wrong") is None

    assert candidates == ["invalid-password-length", "wrong"]


def test_register_requires_terms_acceptance():
    with session_scope() as session, pytest.raises(AuthError, match="Terms"):
        register_user(
            session,
            email="noterms@example.com",
            password="correct horse battery staple",
            name="No Terms",
            accepted_terms=False,
        )


def test_duplicate_email_is_rejected(user_factory):
    user_factory(email="dup@example.com")
    with session_scope() as session, pytest.raises(AuthError, match="already exists"):
        register_user(
            session,
            email="Dup@example.com",
            password="correct horse battery staple",
            name="Duplicate",
            accepted_terms=True,
        )


def test_google_identity_creates_one_user_and_reuses_subject():
    with session_scope() as session:
        first = get_or_create_google_user(
            session,
            subject="google-subject-new",
            email="google-user@example.com",
            name="Google User",
        )
        first_id = first.id
    with session_scope() as session:
        second = get_or_create_google_user(
            session,
            subject="google-subject-new",
            email="google-user-renamed@example.com",
            name="Google User",
        )
        assert second.id == first_id
        assert session.query(User).filter_by(email="google-user@example.com").count() == 1
        assert find_user_by_google_subject(session, "google-subject-new").id == first_id


def test_google_sign_in_rejects_duplicate_email_without_auto_link(user_factory):
    existing = user_factory(email="existing-google-email@example.com")
    with (
        session_scope() as session,
        pytest.raises(AuthError, match="Sign in with your password, then link Google"),
    ):
        get_or_create_google_user(
            session,
            subject="unlinked-google-subject",
            email="Existing-Google-Email@example.com",
            name="Existing User",
        )

    with session_scope() as session:
        stored = session.get(User, existing.id)
        assert stored.google_subject is None
        assert find_user_by_google_subject(session, "unlinked-google-subject") is None


def test_explicit_google_link_succeeds_and_revokes_all_sessions(user_factory):
    user = user_factory(email="link-owner@example.com")
    with session_scope() as session:
        first_token = create_user_session(session, user.id)
        second_token = create_user_session(session, user.id)
        stored = session.get(User, user.id)
        linked = link_google_identity(
            session,
            user=stored,
            subject="explicit-google-subject",
            email="link-owner@example.com",
        )
        assert linked.google_subject == "explicit-google-subject"
        assert linked.google_email == "link-owner@example.com"
        assert get_user_by_session_token(session, first_token) is None
        assert get_user_by_session_token(session, second_token) is None
        assert all(
            auth_session.revoked_at is not None
            for auth_session in session.query(UserSession).filter_by(user_id=user.id).all()
        )


def test_explicit_google_link_rejects_subject_owned_by_another_user(user_factory):
    owner = user_factory(email="google-owner@example.com")
    other = user_factory(email="google-linker@example.com")
    with session_scope() as session:
        owner_record = session.get(User, owner.id)
        link_google_identity(
            session,
            user=owner_record,
            subject="already-owned-google-subject",
            email="google-owner@example.com",
        )

    with session_scope() as session, pytest.raises(AuthError, match="another account"):
        other_record = session.get(User, other.id)
        link_google_identity(
            session,
            user=other_record,
            subject="already-owned-google-subject",
            email="google-linker@example.com",
        )

    with session_scope() as session:
        assert session.get(User, other.id).google_subject is None


def test_explicit_google_link_requires_matching_verified_email(user_factory):
    user = user_factory(email="local-owner@example.com")
    with session_scope() as session, pytest.raises(AuthError, match="same email"):
        stored = session.get(User, user.id)
        link_google_identity(
            session,
            user=stored,
            subject="different-email-subject",
            email="different-google@example.com",
        )

    with session_scope() as session:
        assert session.get(User, user.id).google_subject is None


def test_revoked_session_is_rejected(user_factory):
    user = user_factory()
    with session_scope() as session:
        token = create_user_session(session, user.id)
    with session_scope() as session:
        revoke_user_session(session, token)
        assert get_user_by_session_token(session, token) is None
        stored = session.query(UserSession).filter(UserSession.user_id == user.id).one()
        assert stored.revoked_at is not None


def test_revoke_is_visible_in_the_same_transaction(user_factory):
    user = user_factory()
    with session_scope() as session:
        token = create_user_session(session, user.id)
        assert get_user_by_session_token(session, token) is not None
        revoke_user_session(session, token)
        assert get_user_by_session_token(session, token) is None


def test_revoking_unknown_or_already_revoked_token_is_safe(user_factory):
    user = user_factory()
    with session_scope() as session:
        token = create_user_session(session, user.id)
        revoke_user_session(session, token)
        revoke_user_session(session, token)
        revoke_user_session(session, None)
        revoke_user_session(session, "not-a-real-token")


def test_revoking_one_session_leaves_the_other_valid(user_factory):
    user = user_factory()
    with session_scope() as session:
        first = create_user_session(session, user.id)
        second = create_user_session(session, user.id)
        revoke_user_session(session, first)
        assert get_user_by_session_token(session, first) is None
        assert get_user_by_session_token(session, second).id == user.id


def test_expired_session_is_rejected(user_factory):
    user = user_factory()
    with session_scope() as session:
        token = create_user_session(session, user.id)
        stored = session.query(UserSession).filter(UserSession.user_id == user.id).one()
        stored.expires_at = utcnow() - timedelta(seconds=1)
    with session_scope() as session:
        assert get_user_by_session_token(session, token) is None


def test_inactive_user_cannot_authenticate_or_use_existing_session(user_factory):
    user = user_factory()
    with session_scope() as session:
        token = create_user_session(session, user.id)
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.is_active = False
    with session_scope() as session:
        assert get_user_by_session_token(session, token) is None
        assert (
            authenticate_user(
                session,
                email=user.email,
                password="correct horse battery staple",
            )
            is None
        )


def test_inactive_user_cannot_reserve_generation(user_factory):
    user = user_factory()
    with session_scope() as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.is_active = False
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(user.id, mode="single", provider="template")
    assert blocked.value.code == "unauthorized"


def test_session_token_never_resolves_as_another_user(user_factory):
    owner = user_factory(email="session-owner@example.com")
    stranger = user_factory(email="session-stranger@example.com")
    with session_scope() as session:
        token = create_user_session(session, owner.id)
        resolved = get_user_by_session_token(session, token)
        assert resolved is not None
        assert resolved.id == owner.id
        assert resolved.id != stranger.id


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
    assert get_full_history(stranger.id) == []
    assert update_listing(stranger.id, listing_id, result) is False
    assert delete_listing(stranger.id, listing_id) is False
    assert get_listing_by_id(owner.id, listing_id) is not None
    assert len(get_full_history(owner.id)) == 1


def test_invalid_listing_id_does_not_leak(user_factory):
    user = user_factory()
    assert get_listing_by_id(user.id, "not-a-uuid") is None
    assert update_listing(user.id, "not-a-uuid", {}) is False
    assert delete_listing(user.id, "not-a-uuid") is False


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


def test_edited_draft_is_reaudited_and_only_owner_can_save(user_factory):
    from core.draft_review import draft_export_ready, recheck_edited_draft

    owner = user_factory(email="edit-owner@example.com")
    stranger = user_factory(email="edit-stranger@example.com")
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon pendant",
        platform="etsy",
    )
    listing_id = save_listing(owner.id, original)
    edited = recheck_edited_draft(
        original,
        title="Sterling moon pendant",
        description=original["description"],
        tags=original["tags"],
        explicitly_verified=False,
    )

    assert edited["scores"]["overall"]["status"] == "Verify"
    assert edited["edit_review"]["warnings"]
    assert draft_export_ready(edited) is False
    assert update_listing(stranger.id, listing_id, edited) is False
    assert update_listing(owner.id, listing_id, edited) is True
    assert get_listing_by_id(owner.id, listing_id)["best_title"] == "Sterling moon pendant"

    verified = recheck_edited_draft(
        edited,
        title=edited["best_title"],
        description=edited["description"],
        tags=edited["tags"],
        explicitly_verified=True,
    )
    assert draft_export_ready(verified) is True


def test_unchanged_generated_section_labels_do_not_trigger_edit_warnings():
    from core.draft_review import recheck_edited_draft

    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Moon pendant",
        item_noun="pendant",
        color="blue",
        material="stainless steel",
        size="18-inch chain",
        audience="adults",
        occasion_or_recipient="birthday",
        platform="etsy",
    )
    checked = recheck_edited_draft(
        original,
        title=original["best_title"],
        description=original["description"],
        tags=original["tags"],
        explicitly_verified=False,
    )

    assert checked["edit_review"]["warnings"] == []
    assert checked["edit_review"]["export_ready"] is True


def test_product_event_payloads_store_no_listing_text_or_identity(user_factory):
    from sqlalchemy import select

    from core.events import record_product_event
    from core.models import UsageEvent

    user = user_factory(email="event-privacy@example.com")
    record_product_event(user.id, "draft_edited_saved")
    with session_scope() as session:
        event = session.scalar(select(UsageEvent).where(UsageEvent.kind == "draft_edited_saved"))

    assert event is not None
    assert event.details_json == {}
    assert event.mode == "product"
    assert event.provider == "first_party"
    serialized = str(event.details_json).casefold()
    assert "event-privacy@example.com" not in serialized
    assert "listing" not in serialized
