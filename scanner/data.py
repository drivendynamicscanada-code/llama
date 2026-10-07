"""CSV and optional Alpha Vantage daily inputs; never substitute fake data."""
import csv
from datetime import date
import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .core import Bar, symbol_name, validate


def load_csv(path):
    series = {}
    currencies = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"symbol", "currency", "date", "close", "volume"} <= set(reader.fieldnames or []):
            raise ValueError("CSV requires symbol,currency,date,close,volume columns")
        for line, row in enumerate(reader, 2):
            try:
                symbol = symbol_name(row["symbol"])
                currency = row["currency"].strip().upper()
                if currency not in {"CAD", "USD"}:
                    raise ValueError("Currency must be CAD or USD")
                if symbol in currencies and currencies[symbol] != currency:
                    raise ValueError("One symbol cannot have multiple currencies")
                currencies[symbol] = currency
                bar = Bar(date.fromisoformat(row["date"]), float(row["close"]), int(row["volume"]))
                series.setdefault((symbol, currency), []).append(bar)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid CSV row {line}: {exc}") from None
    if not series:
        raise ValueError("CSV contains no bars")
    return {key: validate(bars) for key, bars in series.items()}


def parse_alpha(payload):
    if not isinstance(payload, dict) or "Time Series (Daily)" not in payload:
        # Do not echo server responses: these can contain the API key or URL.
        raise ValueError("Provider returned no daily data; check symbol, key, entitlement or quota")
    try:
        return validate([Bar(date.fromisoformat(day), float(row["4. close"]),
                             int(row["5. volume"]))
                         for day, row in payload["Time Series (Daily)"].items()])
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError("Provider returned invalid daily bars") from None


def fetch_alpha(symbols):
    key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
    if not key:
        raise ValueError("Set ALPHAVANTAGE_API_KEY to use the optional provider")
    series, errors = {}, []
    for symbol in symbols:
        # v1 live adapter intentionally accepts US/USD listings only.
        if not symbol.isalpha() or not symbol.isascii():
            raise ValueError("Live v1 accepts plain US tickers only; use CSV for Canadian listings")
        params = urlencode(dict(function="TIME_SERIES_DAILY", symbol=symbol,
                                outputsize="compact", apikey=key))
        try:
            with urlopen("https://www.alphavantage.co/query?" + params, timeout=20) as response:
                payload = json.load(response)
            series[(symbol, "USD")] = parse_alpha(payload)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else "Provider request failed (network or invalid JSON)"
            errors.append(dict(symbol=symbol, reason=reason))
    return series, errors
