"""Provider-independent validation and deterministic screening."""
from dataclasses import dataclass
from datetime import date
import math
import re
from statistics import mean


@dataclass(frozen=True)
class Bar:
    date: date
    close: float
    volume: int


@dataclass(frozen=True)
class Rules:
    min_price: float = 2.0
    min_turnover: float = 1_000_000.0
    max_age_days: int = 4

    def __post_init__(self):
        if not all(math.isfinite(x) and x >= 0 for x in
                   (self.min_price, self.min_turnover, self.max_age_days)):
            raise ValueError("Thresholds must be finite and nonnegative")


def symbol_name(value):
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.:-]{0,24}", value):
        raise ValueError("Invalid symbol")
    return value


def validate(bars):
    if not bars:
        raise ValueError("No bars")
    bars = sorted(bars, key=lambda b: b.date)
    if len({b.date for b in bars}) != len(bars):
        raise ValueError("Duplicate session date")
    for b in bars:
        if not math.isfinite(b.close) or b.close <= 0:
            raise ValueError("Close must be finite and positive")
        if isinstance(b.volume, bool) or not isinstance(b.volume, int) or b.volume < 0:
            raise ValueError("Volume must be a nonnegative integer")
    return bars


def evaluate(symbol, currency, bars, as_of, rules):
    # Deliberately exclude same-day bars: they may be partial when run at 7 AM.
    bars = [b for b in validate(bars) if b.date < as_of]
    if len(bars) < 21:
        raise ValueError("Need 21 completed daily bars before as-of date")
    latest, prior = bars[-1], bars[-21:-1]
    age = (as_of - latest.date).days
    if age > rules.max_age_days:
        raise ValueError(f"Stale data: last session {latest.date} ({age} calendar days old)")
    avg_volume = mean(b.volume for b in prior)
    turnover = mean(b.close * b.volume for b in prior)
    if latest.close < rules.min_price or turnover < rules.min_turnover or avg_volume == 0:
        raise ValueError("Below price/liquidity threshold")
    momentum = (latest.close / bars[-6].close - 1) * 100
    relative_volume = latest.volume / avg_volume
    breakout = latest.close > max(b.close for b in prior)
    above_average = latest.close > mean(b.close for b in prior)
    reasons = []
    score = 0
    for passed, points, reason in (
        (momentum > 0, 1, "Positive 5-session momentum"),
        (above_average, 1, "Above prior 20-session average close"),
        (relative_volume >= 1.5, 1, "Volume at least 1.5x prior 20-session average"),
        (breakout, 2, "Above prior 20-session closing high"),
    ):
        if passed:
            score += points
            reasons.append(reason)
    return dict(symbol=symbol, currency=currency, session=latest.date.isoformat(),
                close=latest.close, momentum_5d_pct=round(momentum, 3),
                relative_volume=round(relative_volume, 3),
                avg_turnover_20d=round(turnover, 2), score=score, reasons=reasons)


def scan(series, as_of, rules):
    candidates, excluded = [], []
    for (symbol, currency), bars in sorted(series.items()):
        try:
            result = evaluate(symbol, currency, bars, as_of, rules)
            if result["score"]:
                candidates.append(result)
            else:
                excluded.append(dict(symbol=symbol, reason="No positive screen conditions"))
        except ValueError as exc:
            excluded.append(dict(symbol=symbol, reason=str(exc)))
    candidates.sort(key=lambda r: (-r["score"], -r["momentum_5d_pct"], r["symbol"]))
    return candidates, excluded
