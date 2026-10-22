from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] is True


def test_numeraires_cover_hard_assets(client: TestClient) -> None:
    response = client.get("/api/meta/numeraires")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert {"CNY", "USD", "XAU", "XAU_CNY_G", "WTI", "BRENT", "XAG"} <= ids


def test_overview_shape(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["indices"]) == 4
    assert len(data["fx"]) == 4
    assert len(data["commodities"]) == 5
    assert len(data["yields"]) == 4
    assert len(data["watchlist"]) >= 3
    assert data["market"]["timezone"] == "Asia/Shanghai"
    assert "demo" in data["sources"]


def test_search_by_name_and_code(client: TestClient) -> None:
    by_name = client.get("/api/search", params={"q": "茅台"}).json()["data"]
    by_code = client.get("/api/search", params={"q": "600519"}).json()["data"]
    assert by_name[0]["symbol"] == "SH600519"
    assert any(item["symbol"] == "SH600519" for item in by_code)


def test_instrument_meta_and_snapshot(client: TestClient) -> None:
    meta = client.get("/api/instruments/sh600519").json()["data"]
    assert meta["symbol"] == "SH600519" and meta["currency"] == "CNY"
    snapshot = client.get("/api/instruments/SH600519/snapshot").json()["data"]
    assert snapshot["last"] > 0
    assert len(snapshot["bids"]) == 5 and len(snapshot["asks"]) == 5


def test_chart_in_native_and_gold(client: TestClient) -> None:
    native = client.get(
        "/api/instruments/SH600519/chart", params={"range": "1y"}
    ).json()["data"]
    assert native["meta"]["quoted"] is True
    assert native["meta"]["numeraire"]["id"] == "CNY"
    assert native["bars"][-1]["close"] == native["stats"]["native_last"]
    gold = client.get(
        "/api/instruments/SH600519/chart",
        params={"range": "1y", "numeraire": "XAU"},
    ).json()["data"]
    assert gold["meta"]["numeraire"]["id"] == "XAU"
    assert gold["stats"]["last"] < native["stats"]["last"]


def test_chart_normalize_and_indicators(client: TestClient) -> None:
    payload = client.get(
        "/api/instruments/SH600519/chart",
        params={
            "range": "1y",
            "normalize": "true",
            "numeraire": "XAU_CNY_G",
            "indicators": "ma:20,ma:60,boll:20,macd,rsi:14,kdj",
        },
    ).json()["data"]
    assert payload["stats"]["first"] == 1.0
    assert payload["meta"]["normalized"] is True
    length = len(payload["bars"])
    assert len(payload["indicators"]["ma"]) == 2
    assert len(payload["indicators"]["ma"][0]["values"]) == length
    assert len(payload["indicators"]["macd"]["dif"]) == length
    assert len(payload["indicators"]["rsi"]["values"]) == length
    assert len(payload["indicators"]["kdj"]["k"]) == length
    assert payload["bars"][0]["open"] > 0


def test_chart_downsampled_about_320(client: TestClient) -> None:
    payload = client.get(
        "/api/instruments/SH600519/chart", params={"range": "max"}
    ).json()["data"]
    assert len(payload["bars"]) <= 320
    assert payload["stats"]["points"] > len(payload["bars"])


def test_yield_chart_is_not_converted(client: TestClient) -> None:
    payload = client.get(
        "/api/instruments/UST10Y/chart", params={"numeraire": "XAU"}
    ).json()["data"]
    assert payload["meta"]["quotable"] is False
    assert payload["meta"]["quoted"] is False
    assert 0 < payload["stats"]["last"] < 20


def test_watchlist_add_and_remove(client: TestClient) -> None:
    added = client.post("/api/watchlist/SH601318")
    assert added.status_code == 201
    symbols = client.get("/api/watchlist").json()["data"]["symbols"]
    assert "SH601318" in symbols
    removed = client.delete("/api/watchlist/SH601318")
    assert removed.status_code == 204
    symbols = client.get("/api/watchlist").json()["data"]["symbols"]
    assert "SH601318" not in symbols


def test_custom_index_lifecycle(client: TestClient) -> None:
    unique = f"测试金油比{uuid4().hex[:8]}"
    check = client.post(
        "/api/custom-indices/validate", json={"expression": "XAUUSD / WTIUSD"}
    )
    assert check.status_code == 200
    assert check.json()["data"]["basis"] == "USD"
    created = client.post(
        "/api/custom-indices",
        json={"name": unique, "expression": "XAUUSD / WTIUSD"},
    )
    assert created.status_code == 201
    index_id = created.json()["data"]["id"]
    chart = client.get(f"/api/custom-indices/{index_id}/chart")
    assert chart.status_code == 200
    data = chart.json()["data"]
    assert data["meta"]["chart"] == "line"
    assert len(data["bars"]) == len(data["percentile"])
    assert 0 <= data["stats"]["percentile"] <= 100
    duplicate = client.post(
        "/api/custom-indices",
        json={"name": unique, "expression": "XAUUSD / WTIUSD"},
    )
    assert duplicate.status_code == 400
    deleted = client.delete(f"/api/custom-indices/{index_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/custom-indices/{index_id}").status_code == 404


def test_custom_index_rejects_bad_expressions(client: TestClient) -> None:
    for expression in ("XAUUSD /", "@不存在的指数", "XAUUSD + UST10Y", "42", "sum(XAUUSD)"):
        response = client.post(
            "/api/custom-indices/validate", json={"expression": expression}
        )
        assert response.status_code == 400, expression


def test_custom_index_rejects_bad_name(client: TestClient) -> None:
    response = client.post(
        "/api/custom-indices",
        json={"name": "有 空格", "expression": "XAUUSD / WTIUSD"},
    )
    assert response.status_code == 400


def test_dca_backtest(client: TestClient) -> None:
    response = client.get(
        "/api/tools/dca",
        params={
            "symbol": "SH600519",
            "start": "2024-01-01",
            "amount": "1000",
            "day": "5",
            "numeraire": "CNY",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metrics"]["invested"] > 0
    assert data["metrics"]["purchases"] > 10
    assert data["metrics"]["final_value"] > 0
    assert data["purchases"][0]["time"].startswith("2024-01")


def test_dca_rejects_yield(client: TestClient) -> None:
    response = client.get(
        "/api/tools/dca", params={"symbol": "UST10Y", "amount": "1000"}
    )
    assert response.status_code == 400


def test_correlation_matrix(client: TestClient) -> None:
    response = client.get(
        "/api/tools/correlation",
        params={"symbols": "SH600519,SZ300750,XAUUSD", "window": "120"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["symbols"]) == 3
    assert data["matrix"]["SH600519"]["SH600519"] == 1.0
    assert data["matrix"]["SH600519"]["SZ300750"] == data["matrix"]["SZ300750"]["SH600519"]
    assert data["window"] == 120


def test_correlation_needs_two_symbols(client: TestClient) -> None:
    response = client.get("/api/tools/correlation", params={"symbols": "XAUUSD"})
    assert response.status_code == 400


def test_compound(client: TestClient) -> None:
    response = client.post(
        "/api/tools/compound",
        json={
            "principal": 100000,
            "monthly": 2000,
            "annual_rate_pct": 8,
            "years": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["final_value"] > data["contributions"] > 0
    assert len(data["points"]) == 10


def test_unknown_api_route_returns_json_error(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_snapshot_timestamp_carries_offset(client: TestClient) -> None:
    snapshot = client.get("/api/instruments/SH600519/snapshot").json()["data"]
    assert snapshot["ts"].endswith("+08:00")


def test_unknown_symbol_is_rejected(client: TestClient) -> None:
    response = client.get("/api/instruments/BTC")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_bare_api_path_returns_json(client: TestClient) -> None:
    response = client.get("/api")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_overview_reflects_new_custom_index(client: TestClient) -> None:
    created = client.post(
        "/api/custom-indices",
        json={"name": "测试金银比", "expression": "XAUUSD / XAGUSD"},
    )
    assert created.status_code == 201
    index_id = created.json()["data"]["id"]
    overview = client.get("/api/overview").json()["data"]
    assert any(card["id"] == index_id for card in overview["custom_indices"])
    client.delete(f"/api/custom-indices/{index_id}")


def test_nested_custom_index(client: TestClient) -> None:
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    base = client.post(
        "/api/custom-indices",
        json={"name": f"基础金油{suffix}", "expression": "XAUUSD / WTIUSD"},
    )
    assert base.status_code == 201
    base_id = base.json()["data"]["id"]
    nested = client.post(
        "/api/custom-indices",
        json={"name": f"嵌套金油{suffix}", "expression": f"@{'基础金油' + suffix} / XAUUSD"},
    )
    assert nested.status_code == 201
    nested_id = nested.json()["data"]["id"]
    chart = client.get(f"/api/custom-indices/{nested_id}/chart")
    assert chart.status_code == 200
    assert chart.json()["data"]["references"][0]["kind"] == "custom"
    client.delete(f"/api/custom-indices/{nested_id}")
    client.delete(f"/api/custom-indices/{base_id}")


def test_yield_spread_expression(client: TestClient) -> None:
    check = client.post(
        "/api/custom-indices/validate", json={"expression": "UST10Y - UST2Y"}
    )
    assert check.status_code == 200
    data = check.json()["data"]
    assert data["basis"] == "%"
    assert 0 < data["last"] < 10
