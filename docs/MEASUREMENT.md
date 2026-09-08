# Content-free repair measurement

The continuation checkpoint is **hold**. No authorized production analytics or
support-load evidence was available in this session. Draft volume and successful
tests do not establish retention, willingness to pay, or business validation.

`python -m scripts.acquisition_report --since YYYY-MM-DD` prints aggregate counts
only. `--since` selects the signup cohort for the unique-account measures; the
separate raw event section filters event time. `--include-fixtures` is a diagnostic
view that includes all classifications and must not be cited as customer demand.

| Measure | Evidence and limitations |
|---|---|
| First draft | One database-unique milestone when generation, saved draft, and quota completion commit together. Deleting a draft does not erase activation. Historical first-draft events are backfilled once at their earliest observed timestamp. |
| First output used | One milestone after an authenticated copy acknowledgment with a signed one-hour user/draft/action capability, or a server download callback with bounded owned saved-record IDs and current export validation. No draft text enters events. Browser clipboard success and file delivery cannot be independently proven by the server; this is an action signal. |
| Second activity session | First authenticated activity after at least 30 minutes of inactivity across that account's sessions. This uses the usual idle-time activity-session definition, not a count of login cookies. A continuously active workspace is not a return. |
| Day-7 return | Authenticated activity in `[7, 8)` days after first draft. The denominator contains only activations whose entire window has elapsed. Backfilled activations are excluded: their return window was not instrumented, so missing events cannot be called losses. |
| Actual paid conversion | First signed, configured-price Checkout event with `payment_status=paid`, positive `amount_total`, and `livemode=true`. Trials, zero-cost Checkout, an active subscription, and success redirects do not count. Signed test payments have a separate milestone. Cancellation does not erase the historical conversion. |
| Recurring generation errors | Accounts with at least two server-recorded failed generation attempts in the reporting window. This is not total support load or a complete OAuth/provider incident count. |

`product_milestones` has a primary key on `(user_id, kind)`; concurrent first events
use a database conflict-safe insert. The existing `usage_events` product records
contain only an allowlisted event name, internal owner ID, server timestamps, and
empty details. No seller/customer content, email, or arbitrary browser payload is
stored in these events. They are first-party operational records, not ad pixels.

New development/test accounts and container smoke accounts are marked fixtures.
Normal production signup explicitly records a non-fixture. Pre-migration accounts
start with classification `NULL`; the report shows how many are excluded as
unclassified instead of silently calling them customers. A trusted operator with
database access can classify a known account using:

```sh
python -m scripts.classify_measurement_account --account-id UUID --classification fixture
# Use --classification customer only after confirming it is not a test account.
```

The helper changes only classification, rejects unknown IDs, and prints no account
identifier or content. It is not an HTTP endpoint. Existing accounts, ownership,
plans, draft IDs, and entitlements are untouched. No production classifications
were changed during this repair.

After an authorized deployment and an observed pilot, review activation-to-output,
the mature day-7 cohort, genuine payments and cancellations, recurring errors, and
actual mailbox support effort together. Decide whether a narrow Etsy workflow is
worth another experiment. Reusable verified facts and bulk variant review remain
an unimplemented hypothesis; quota size alone is not proven subscription value.
