from api.main import app, frontend, health, market_screener


def test_api_health_smoke():
    payload = health()

    assert payload["status"] == "ok"
    assert payload["app"] == "CMMTrader"
    assert payload["paperOnly"] is True


def test_frontend_fallback_before_or_after_build():
    response = frontend("")

    assert response is not None
    assert any(route.path == "/api/health" for route in app.routes)
    assert any(route.path == "/api/backtest-batch" for route in app.routes)


def test_fixture_market_screener_contract():
    payload = market_screener(limit=3, data_mode="fixture")

    assert payload["source"] == "fixture"
    assert len(payload["rows"]) == 3
    assert payload["warnings"] == []
    assert set(payload["rows"][0]) >= {
        "symbol",
        "market",
        "source",
        "price",
        "change24h",
        "rsi4h",
        "rsi1h",
        "macd1d",
        "macd4h",
        "macd1h",
        "updatedAt",
    }
