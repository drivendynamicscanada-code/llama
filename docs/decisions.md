# Prototype decisions and boundaries

## Verified starting point

Inspected main at `ca7f32203a8f82b1e3e6d26b51fac3355ec863cd`: its only file
was a one-byte blank `llama`, created August 17, 2025. No open issues or pull
requests were returned. There was no code, setup or AGENTS.md to preserve.
The original blank file is retained to avoid an unrelated deletion.

## Minimum architecture chosen

One Python process, standard library only, no database, service, UI or language
model. Flow: explicit input source → validated daily bars → completed-session
cutoff → freshness/liquidity filters → explainable score → console/JSON report.
The same scoring function handles both CSV and online inputs. JSON is the small
integration boundary for a future dashboard or alert sender.

Daily close/volume is the first data flow because the intended holding period is
days and it can be exercised offline. Transparent calculations establish something
testable before adding news interpretation or an AI component. This is watchlist
screening of supplied symbols, not discovery across all Canadian/US exchanges.

## Implemented versus pending

| Area | Working now | Pending decision or future work |
| --- | --- | --- |
| Input | CSV, synthetic demo, optional Alpha Vantage daily adapter | Confirm provider, budget, licensing, exchanges and credentials for ongoing live use |
| Universe | All symbols in CSV; up to five US tickers in online mode | Actual watchlist and Canadian live symbol mapping |
| Screening | Documented, configurable liquidity and momentum rules | User preferences plus historical evaluation before relying on the ranking |
| Output | Terminal and JSON with source/date/errors | Choose notification destination if alerts are wanted |
| Cadence | Manual run; CI executes offline tests/demo | Prior 7 AM Edmonton preference is context only; no scheduler deployed or new automation created |
| Account | Currency labels only | Confirm current capital, broker, FX/fees and risk limits before adding sizing |
| News/AI | Absent, no fabricated scores or catalysts | Source, timestamps, citation/provenance and evaluation design |
| Trading | Absent | No brokerage connection or automatic execution in this scope |

Earlier discussion mentioned a small CAD account and trades held for days. Those
amounts are not hard-coded as current balances. The example thresholds and demo
prices are explicitly implementation defaults, not inferred user approvals.

## Next useful increment

Validate one real data export or a credentialed provider response against known
closing prices. Then confirm the intended Canadian/US watchlist and data provider.
Before deployment: add exchange-session calendars, corporate-action handling,
provider-aware rate limits/caching and observability. Before calling this a trading
strategy: evaluate historical out-of-sample results including costs, survivorship
bias and drawdowns. Only then add sizing or schedule an unattended report.

## Validation scope

Offline tests cover exact metrics, baseline exclusion, same-day/future exclusion,
insufficient/stale data, zero liquidity, invalid CSV/numbers, deterministic ordering,
provider schema and quota errors, partial failure, secret redaction, CLI and JSON.
No claim of a credentialed live integration test, forecast accuracy or investment
performance is made. GitHub CI checks the offline prototype, not live availability.
