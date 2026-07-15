from __future__ import annotations

from .models import Candidate, SetupScore, TradeThesis, ValidationResult


class AlertFormatter:
    def format(
        self,
        candidate: Candidate,
        thesis: TradeThesis,
        validation: ValidationResult,
        score: SetupScore | None = None,
    ) -> str:
        targets = ", ".join(_price(target) for target in thesis.targets) or "n/a"
        evidence = "\n".join(f"- {item}" for item in thesis.evidence) or "- n/a"
        status = "APPROVED" if validation.approved else "NOT APPROVED"
        reasons = "\n".join(f"- {item}" for item in validation.reasons) or "- Passed"
        quality = alert_grade(thesis, validation, score)
        market = []
        if candidate.volume_24h_usd is not None:
            market.append(f"24h volume: {_usd(candidate.volume_24h_usd)}")
        if candidate.open_interest_change_24h_pct is not None:
            market.append(f"OI 24h: {candidate.open_interest_change_24h_pct:.2f}%")
        if score is not None:
            market.append(f"rank score: #{score.rank} / {score.score:.1f}")
            if score.relative_volume is not None:
                market.append(f"15m rel vol: {score.relative_volume:.2f}x")
        market_text = " | ".join(market) or "Market context: n/a"
        signal_note = ""
        if thesis.signal.value == "watch":
            signal_note = f"Status: WATCH only - not confirmed entry ({thesis.direction.upper()}).\n"
        if thesis.signal.value == "enter":
            signal_note = f"Status: ENTER - rules confirm {thesis.direction.upper()} entry conditions.\n"
        tv_link = tradingview_link(candidate.route_symbol)
        trade_link = candidate.trading_link or "n/a"
        signal_label = (
            f"SCALP {thesis.signal.value.upper()} {thesis.direction.upper()}"
            if thesis.setup.value == "alma_cci_scalp"
            else f"{thesis.signal.value.upper()} {thesis.direction.upper()}"
        )
        return (
            f"Coach Miranda Miner\n"
            f"Symbol: {candidate.route_symbol} on {candidate.exchange_id}\n"
            f"Setup: {thesis.setup.value} | Signal: {signal_label} | "
            f"{status} | Grade: {quality}\n"
            f"{signal_note}"
            f"Direction: {thesis.direction} | Confidence: {thesis.confidence:.2f}\n"
            f"{market_text}\n"
            f"Entry: {_price(thesis.entry)} | Stop: {_price(thesis.stop_loss)} | "
            f"Targets: {targets}\n"
            f"Risk/Reward: {_ratio(thesis.risk_reward)}\n"
            f"TradingView: {tv_link}\n"
            f"Trade Link: {trade_link}\n\n"
            f"Evidence:\n{evidence}\n\n"
            f"Validation:\n{reasons}"
        )


def alert_grade(
    thesis: TradeThesis,
    validation: ValidationResult,
    score: SetupScore | None = None,
) -> str:
    if thesis.direction == "none" or thesis.setup.value == "none":
        return "D"
    rank_score = score.score if score is not None else thesis.confidence * 100
    relative_volume = score.relative_volume if score is not None else None
    strong_volume = relative_volume is not None and relative_volume >= 1.5
    enter = thesis.signal.value == "enter"
    watch_or_enter = thesis.signal.value in {"watch", "enter"}

    if (
        validation.approved
        and enter
        and thesis.confidence >= 0.78
        and rank_score >= 75
        and strong_volume
    ):
        return "A+"
    if watch_or_enter and (validation.approved or enter) and thesis.confidence >= 0.72 and rank_score >= 65:
        return "A"
    if watch_or_enter and thesis.confidence >= 0.65 and rank_score >= 45:
        return "B"
    if thesis.confidence >= 0.55:
        return "C"
    return "D"


def grade_rank(grade: str) -> int:
    return {"A+": 4, "A": 3, "B": 2, "C": 1, "D": 0}.get(grade.upper(), 0)


def tradingview_link(symbol: str) -> str:
    base = symbol.split("/")[0].upper()
    return f"https://www.tradingview.com/chart/?symbol=COINBASE%3A{base}USD"


def telegram_buttons(candidate: Candidate, dashboard_url: str | None = None) -> list[dict[str, str]]:
    buttons = [{"text": "TradingView", "url": tradingview_link(candidate.route_symbol)}]
    if candidate.trading_link:
        buttons.append({"text": "Trading Page", "url": candidate.trading_link})
    if dashboard_url:
        buttons.append({"text": "Dashboard", "url": dashboard_url})
    return buttons


def _quality(confidence: float) -> str:
    if confidence >= 0.8:
        return "A"
    if confidence >= 0.7:
        return "B"
    if confidence >= 0.6:
        return "C"
    return "D"


def _price(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


def _usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def _ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
