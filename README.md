# Llama: daily stock watchlist prototype

A small command-line scanner for researching trades held for days. It reads daily
closing prices and volume, screens a supplied universe and explains its ranking.
It does not predict returns, recommend an allocation or place trades.

## Run in one minute

Requires Python 3.11+ on Linux/macOS (Python 3.12 is tested). No third-party runtime
packages or API key are needed for the demo or CSV flow. On systems without an IANA
timezone database, install `tzdata` or supply `--as-of` explicitly.

```bash
git clone https://github.com/drivendynamicscanada-code/llama.git
cd llama
git checkout feat/stock-scanner-prototype
python -m scanner --demo --out reports/demo.json
python -m unittest discover -s tests -v
```

The demo uses **fictional prices and symbols**, frozen at an exclusive cutoff of
2026-10-06. It produces one ranked candidate (`DEMO-UP`) and explains why the other
two were excluded. It never fetches data and is not a current market scan.

## Use actual daily data

Export at least 21 completed sessions per symbol from your data source using:

```csv
symbol,currency,date,close,volume
EXAMPLE.TO,CAD,2026-10-05,25.10,150000
```

That single row illustrates the schema, not sufficient history. Dates are exchange
session dates; volume is whole shares; use one consistent price/volume adjustment
basis throughout each symbol. Duplicate dates, missing columns, nonfinite prices,
negative volumes and inconsistent currency labels are rejected. CSV validation
fails the whole import rather than silently skipping corrupt rows.

```bash
python -m scanner --csv /path/to/daily.csv --out reports/watchlist.json
python -m scanner --csv /path/to/daily.csv --as-of 2026-10-06
```

Default cutoff is today's date in `America/Edmonton`. Only sessions **before** that
date are used, including when the command runs after the close. A manual historical
cutoff is available for reproducibility; this is not a backtesting engine.

## Optional online input

The implemented adapter requests Alpha Vantage `TIME_SERIES_DAILY` with
`outputsize=compact`. See the [official API contract](https://www.alphavantage.co/documentation/#daily).
You must obtain your own key and confirm your data entitlement, usage terms and
quota. No subscription has been selected or purchased. Provider errors never
fall back to demo data. Requests have a 20-second timeout and are not retried.

Set `ALPHAVANTAGE_API_KEY` in your environment (never commit it), then:

```bash
python -m scanner --alpha-vantage --symbols IBM,MSFT --out reports/watchlist.json
```

These are example input symbols, not recommendations. This adapter is deliberately
limited to a user-supplied list of up to five **US listings quoted in USD**. Plain
alphabetic ticker syntax is enforced, but exchange/currency identity is not
looked up: verify the symbols are US listings before supplying them. Canadian
listings currently use CSV. A provider response labels USD based on this input
contract, not an FX conversion. API quotas can still be exceeded across runs;
partial failures are reported and exit with code 2. No cache or scheduler exists.

The adapter has mocked contract/error tests; a credentialed live scan has **not**
been validated. Daily prices are unadjusted: splits and other corporate actions
can create false momentum/breakout signals. Confirm these before using results.

## What the screen does

Defaults are engineering examples, not an optimized or validated trading strategy:

| Rule | Default |
| --- | --- |
| Minimum latest close | 2 units of listing currency |
| Prior 20-session average close × volume | At least 1,000,000 units of listing currency/day |
| Maximum age of latest eligible session | 4 calendar days |
| Positive five-session price change | +1 point |
| Latest close above prior 20-session average | +1 point |
| Latest volume ≥1.5× prior 20-session average | +1 point |
| Latest close above prior 20-session closing high | +2 points |

Baselines exclude the latest signal session. Candidates need at least one point;
sort order is score, then five-session percentage change, then symbol. A 5/5 score
does **not** mean five expected percentage points or a likelihood of profit.
Turnover is an approximation, not true traded value or spread-based liquidity.
CAD and USD liquidity thresholds are applied in their own currencies and are not
directly comparable. Currency is always shown; account affordability is not inferred.

Flags: `--min-price`, `--min-turnover`, `--max-age-days`, `--as-of`, `--out`.
Freshness is a calendar-day guard, not an exchange calendar or missing-session
audit; holidays and suspensions require checking. No live quotes, news catalysts,
earnings, bid/ask spreads, FX rates, costs, slippage or position sizing are included.

## Structure and output

- `scanner/data.py`: CSV validation and optional online adapter.
- `scanner/core.py`: typed bars, rules, metrics and deterministic ranking.
- `scanner/__main__.py`: CLI, console results and versioned JSON report.
- `examples/demo.csv`: fixed, synthetic example input.
- `tests/test_scanner.py`: arithmetic, dates, bad data, provider failures and CLI checks.
- `.github/workflows/test.yml`: tests and offline demo only; no API secret required.
- `docs/decisions.md`: scope, remaining decisions and the next useful increment.

JSON reports include source, UTC generation time, cutoff, thresholds, candidates,
exclusions and request errors. `status=ok` describes input processing, not trading
quality. An empty result is valid. Exit 0 means the scan finished (possibly with
stale/illiquid symbols excluded); exit 2 means bad input or any provider failure.
Reports and local secrets are git-ignored. Existing output paths are overwritten.
