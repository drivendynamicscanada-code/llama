"""Run with python -m scanner --demo."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from .core import Rules, scan, symbol_name
from .data import fetch_alpha, load_csv


def parser():
    p = argparse.ArgumentParser(description="Daily watchlist screen; no orders or return predictions")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Use fictional, fixed-date example bars")
    source.add_argument("--csv", type=Path, help="Read real daily bars from a CSV export")
    source.add_argument("--alpha-vantage", action="store_true", help="Fetch US daily bars using your API key")
    p.add_argument("--symbols", help="Comma-separated US tickers; required for Alpha Vantage")
    p.add_argument("--as-of", type=date.fromisoformat, help="Exclusive session cutoff YYYY-MM-DD")
    p.add_argument("--min-price", type=float, default=2)
    p.add_argument("--min-turnover", type=float, default=1_000_000)
    p.add_argument("--max-age-days", type=int, default=4)
    p.add_argument("--out", type=Path, help="Write a machine-readable JSON report")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        rules = Rules(args.min_price, args.min_turnover, args.max_age_days)
        errors = []
        if args.symbols and not args.alpha_vantage:
            raise ValueError("--symbols is only supported with --alpha-vantage")
        if args.demo:
            series = load_csv(Path(__file__).resolve().parent.parent / "examples/demo.csv")
            as_of = args.as_of or date(2026, 10, 6)
            source = "SYNTHETIC DEMO — fictional symbols and prices"
        else:
            as_of = args.as_of or datetime.now(ZoneInfo("America/Edmonton")).date()
            if args.csv:
                series = load_csv(args.csv)
                source = "USER CSV — source, adjustment and currency labels are user-supplied"
            else:
                if not args.symbols:
                    raise ValueError("--alpha-vantage requires --symbols (small US watchlist)")
                symbols = list(dict.fromkeys(symbol_name(s) for s in args.symbols.split(",")))
                if len(symbols) > 5:
                    raise ValueError("Prototype live scans are limited to 5 symbols per run")
                series, errors = fetch_alpha(symbols)
                source = "ALPHA VANTAGE — unadjusted daily bars, US/USD listings only"
        candidates, excluded = scan(series, as_of, rules)
        report = dict(schema_version=1, source=source,
                      generated_at=datetime.now(timezone.utc).isoformat(),
                      as_of_exclusive=as_of.isoformat(), rules=vars(rules),
                      status="partial" if errors and series else "failed" if errors else "ok",
                      candidates=candidates, excluded=excluded, errors=errors,
                      limitations=["Heuristic score, not expected return or buy advice",
                                   "Daily data only; same-day bars excluded",
                                   "No FX conversion, sizing, news, corporate-action checks or order execution"])
        print(source)
        print(f"Sessions before {as_of} | status: {report['status']}")
        print("Score is 0–5 screening points, NOT a probability or forecast.\n")
        for row in candidates:
            print(f"{row['symbol']:12} {row['currency']} {row['close']:.2f} | {row['session']} | "
                  f"score {row['score']}/5 | 5-session {row['momentum_5d_pct']:+.2f}% | "
                  f"volume {row['relative_volume']:.2f}x")
            print("  " + "; ".join(row["reasons"]))
        if not candidates:
            print("No candidates passed this screen.")
        for row in excluded + errors:
            print(f"Excluded/error: {row['symbol']}: {row['reason']}")
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            print(f"\nJSON report: {args.out}")
        return 2 if errors else 0
    except (ValueError, OSError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
