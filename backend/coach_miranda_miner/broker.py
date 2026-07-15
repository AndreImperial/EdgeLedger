from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaperAccount:
    cash: float
    base_position: float = 0.0


@dataclass(frozen=True)
class PaperFill:
    action: str
    quantity: float
    price: float
    notional_usd: float
    message: str


class PaperBroker:
    def __init__(self, starting_cash: float) -> None:
        self.account = PaperAccount(cash=starting_cash)

    def place_order(self, action: str, price: float, notional_usd: float) -> PaperFill:
        quantity = notional_usd / price

        if action == "buy":
            if self.account.cash < notional_usd:
                return PaperFill(action, 0.0, price, 0.0, "Insufficient paper cash.")
            self.account.cash -= notional_usd
            self.account.base_position += quantity
            return PaperFill(action, quantity, price, notional_usd, "Paper buy filled.")

        if action == "sell":
            quantity = min(quantity, self.account.base_position)
            notional = quantity * price
            if quantity <= 0:
                return PaperFill(action, 0.0, price, 0.0, "No paper position to sell.")
            self.account.cash += notional
            self.account.base_position -= quantity
            return PaperFill(action, quantity, price, notional, "Paper sell filled.")

        return PaperFill("hold", 0.0, price, 0.0, "No paper order placed.")

