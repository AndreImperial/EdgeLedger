from __future__ import annotations

import requests


class NewsProvider:
    def summarize(self, base: str) -> str:
        raise NotImplementedError


class EmptyNewsProvider(NewsProvider):
    def summarize(self, base: str) -> str:
        return "News adapter not configured; no fundamental veto detected."


class CryptoPanicNewsProvider(NewsProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def summarize(self, base: str) -> str:
        response = requests.get(
            "https://cryptopanic.com/api/developer/v2/posts/",
            params={
                "auth_token": self.api_key,
                "currencies": base,
                "kind": "news",
                "public": "true",
            },
            timeout=30,
        )
        response.raise_for_status()
        posts = response.json().get("results", [])[:8]
        if not posts:
            return f"No recent CryptoPanic headlines found for {base}."
        headlines = []
        for post in posts:
            title = post.get("title")
            sentiment = post.get("votes", {})
            if title:
                headlines.append(f"{title} | votes={sentiment}")
        return "\n".join(headlines)
