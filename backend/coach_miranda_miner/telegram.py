from __future__ import annotations

from typing import Any

import requests


class TelegramAlerter:
    def __init__(self, bot_token: str | None, chat_id: str | None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return self.bot_token is not None and self.chat_id is not None

    def send(self, text: str, buttons: list[dict[str, str]] | None = None) -> bool:
        if not self.configured:
            return False

        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [[button] for button in buttons],
            }

        response = requests.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return True
