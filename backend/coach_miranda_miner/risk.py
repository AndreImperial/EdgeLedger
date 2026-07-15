from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    notional_usd: float


class RiskManager:
    def __init__(self, max_position_usd: float, max_daily_loss_usd: float) -> None:
        self.max_position_usd = max_position_usd
        self.max_daily_loss_usd = max_daily_loss_usd

    def evaluate(self, action: str, daily_pnl: float) -> RiskDecision:
        if action == "hold":
            return RiskDecision(False, "No trade requested.", 0.0)

        if daily_pnl <= -abs(self.max_daily_loss_usd):
            return RiskDecision(False, "Daily loss limit reached.", 0.0)

        return RiskDecision(True, "Risk checks passed.", self.max_position_usd)

