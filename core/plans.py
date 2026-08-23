"""Single source of truth for plan entitlements and display copy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanPolicy:
    name: str
    daily_generations: int
    monthly_generations: int
    per_minute_generations: int
    daily_llm_generations: int
    bulk_rows_per_job: int
    display_price: str


PLANS: dict[str, PlanPolicy] = {
    "free": PlanPolicy("Free", 8, 40, 8, 4, 5, "$0"),
    "starter": PlanPolicy("Starter", 50, 1_000, 30, 25, 25, "$12/month"),
    "pro": PlanPolicy("Pro", 250, 5_000, 120, 100, 100, "$29/month"),
    "agency": PlanPolicy("Agency", 1_000, 25_000, 300, 500, 250, "$79/month"),
}

PAID_PLANS = ("starter", "pro", "agency")
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing"})
# Existing Stripe subscriptions that must be changed in the Customer Portal,
# not by starting a second Checkout session.
PORTAL_MANAGED_STATUSES = frozenset(
    {"active", "trialing", "past_due", "unpaid", "incomplete", "paused"}
)
FAILED_PAYMENT_STATUSES = frozenset({"past_due", "unpaid"})


def get_plan_policy(plan: str) -> PlanPolicy:
    return PLANS.get(plan, PLANS["free"])


def subscription_must_use_portal(status: str | None, stripe_subscription_id: str | None) -> bool:
    return bool(stripe_subscription_id) and status in PORTAL_MANAGED_STATUSES
