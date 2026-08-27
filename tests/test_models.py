from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from probalytics import (
    ClickHouseClient,
    Market,
    MarketType,
    OrderbookSnapshot,
    Platform,
    ProbalyticsClient,
)
from probalytics._frames import dataframe_to_frame, normalize_time
from probalytics._filters import market_filter
from probalytics.clickhouse import _fill_row


def market_payload() -> dict:
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "platform": "POLYMARKET",
        "platform_id": "0xmarket",
        "slug": "market",
        "url": "https://example.com",
        "title": "Will it happen?",
        "description": "",
        "category": "Politics",
        "tags": ["tag"],
        "market_type": "BINARY",
        "outcomes": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "platform_id": "yes",
                "name": "Yes",
                "index": 0,
            }
        ],
        "status": "ACTIVE",
        "created_at": "2026-03-15T00:00:00Z",
        "opened_at": "2026-03-15T00:00:00Z",
        "closes_at": None,
        "resolves_at": None,
        "end_date": None,
        "reset_at": None,
        "resolution": None,
        "source_block_number": 0,
        "source_tx_hash": "",
        "indexed_at": "2026-03-15T00:00:01Z",
    }


def test_market_is_first_class_filter() -> None:
    market = Market.model_validate(market_payload())

    market_id, market_platform_id, platform = market_filter(market, None, None, None)

    assert str(market_id) == market_payload()["id"]
    assert market_platform_id == "0xmarket"
    assert platform == "POLYMARKET"


def test_public_enums_only_include_current_values() -> None:
    assert set(Platform) == {Platform.POLYMARKET, Platform.KALSHI}
    assert MarketType.PERPETUAL == "PERPETUAL"

    with pytest.raises(ValueError):
        Platform("PREDICTIT")
    with pytest.raises(ValueError):
        MarketType("UNKNOWN")


def test_orderbook_snapshot_models_current_quality_fields() -> None:
    snapshot = OrderbookSnapshot.model_validate(
        {
            "market_id": "550e8400-e29b-41d4-a716-446655440000",
            "market_platform_id": "0xmarket",
            "platform": "POLYMARKET",
            "outcome": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "platform_id": "yes",
                "name": "Yes",
                "index": 0,
            },
            "bids": [{"price": "0.44", "size": "10"}],
            "asks": [{"price": "0.46", "size": "8"}],
            "timestamp": "2026-03-15T00:00:00Z",
            "indexed_at": "2026-03-15T00:00:00.001Z",
            "hash": 101,
            "state": "VERIFIED",
            "continuity": "RESET",
            "path_index": 0,
        }
    )

    assert snapshot.state == "VERIFIED"
    assert snapshot.continuity == "RESET"
    assert snapshot.hash == 101
    assert snapshot.path_index == 0


def test_dataframe_to_polars_preserves_struct() -> None:
    df = dataframe_to_frame(
        {
            "id": ["fill-id"],
            "outcome": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "platform_id": "yes",
                    "name": "Yes",
                    "index": 0,
                }
            ],
        },
        frame="polars",
    )

    assert df["outcome"].struct.field("name").to_list() == ["Yes"]
    assert df["outcome"].struct.field("index").to_list() == [0]


def test_dataframe_to_pandas_preserves_nested_object() -> None:
    outcome = {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "platform_id": "yes",
        "name": "Yes",
        "index": 0,
    }

    df = dataframe_to_frame({"id": ["fill-id"], "outcome": [outcome]}, frame="pandas")

    assert df.loc[0, "outcome"] == outcome


def test_normalize_time_parses_rfc3339_string() -> None:
    value = normalize_time("2026-03-15T00:00:00Z")

    assert value.isoformat() == "2026-03-15T00:00:00+00:00"


def test_normalize_time_treats_naive_datetime_as_utc() -> None:
    value = normalize_time(datetime(2026, 3, 15, 12, 30))

    assert value == datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc)


def test_normalize_time_rejects_invalid_string() -> None:
    with pytest.raises(ValueError, match="invalid datetime string"):
        normalize_time("not-a-date")


def test_client_wraps_backend() -> None:
    class Backend:
        def markets(self, **kwargs):
            return [Market.model_validate(market_payload())]

    client = ProbalyticsClient(Backend())

    assert client.markets()[0].platform == "POLYMARKET"
    assert client.markets()[0].platform_id == "0xmarket"


def test_market_can_query_fills_with_bound_client() -> None:
    class Backend:
        def markets(self, **kwargs):
            return [Market.model_validate(market_payload())]

        def fills_frame(self, **kwargs):
            self.fills_kwargs = kwargs
            return "fills"

    backend = Backend()
    client = ProbalyticsClient(backend, frame="pandas")
    market = client.markets()[0]

    fills = market.fills(taker_side="BUY", limit=10)

    assert fills == "fills"
    assert backend.fills_kwargs["market"] is market
    assert backend.fills_kwargs["taker_side"] == "BUY"
    assert backend.fills_kwargs["limit"] == 10
    assert backend.fills_kwargs["frame"] == "pandas"


def test_market_can_query_orderbook_snapshots_with_bound_client() -> None:
    class Backend:
        def markets(self, **kwargs):
            return [Market.model_validate(market_payload())]

        def orderbook_snapshots(self, **kwargs):
            self.orderbook_kwargs = kwargs
            return "snapshots"

    backend = Backend()
    client = ProbalyticsClient(backend)
    market = client.markets()[0]

    snapshots = market.orderbook_snapshots(
        start_time="2026-03-15T00:00:00Z",
        end_time="2026-03-15T00:01:00Z",
        state="VERIFIED",
        continuity="RESET",
        frame="pandas",
    )

    assert snapshots == "snapshots"
    assert backend.orderbook_kwargs["market"] is market
    assert backend.orderbook_kwargs["start_time"] == "2026-03-15T00:00:00Z"
    assert backend.orderbook_kwargs["end_time"] == "2026-03-15T00:01:00Z"
    assert backend.orderbook_kwargs["state"] == "VERIFIED"
    assert backend.orderbook_kwargs["continuity"] == "RESET"
    assert backend.orderbook_kwargs["frame"] == "pandas"


def test_market_requires_client_for_convenience_queries() -> None:
    market = Market.model_validate(market_payload())

    with pytest.raises(ValueError, match="market is not bound to a client"):
        market.fills()


def test_client_uses_global_frame_default() -> None:
    class Backend:
        def query(self, sql, *, parameters=None, frame="polars"):
            self.frame = frame
            return []

    backend = Backend()
    client = ProbalyticsClient(backend, frame="pandas")

    client.query("SELECT 1")

    assert backend.frame == "pandas"


def test_client_frame_override_wins_over_global_default() -> None:
    class Backend:
        def query(self, sql, *, parameters=None, frame="polars"):
            self.frame = frame
            return []

    backend = Backend()
    client = ProbalyticsClient(backend, frame="pandas")

    client.query("SELECT 1", frame="polars")

    assert backend.frame == "polars"


def test_client_rejects_invalid_global_frame() -> None:
    with pytest.raises(ValueError, match="frame must be 'polars' or 'pandas'"):
        ProbalyticsClient(object(), frame="arrow")


def test_client_closes_backend_with_context_manager() -> None:
    class Backend:
        closed = False

        def close(self):
            self.closed = True

    backend = Backend()

    with ProbalyticsClient(backend) as client:
        assert client.clickhouse is backend

    assert backend.closed is True


def test_client_from_env_reads_connection_settings(monkeypatch) -> None:
    captured = {}

    def fake_from_clickhouse(cls, **kwargs):
        captured.update(kwargs)
        return "client"

    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_HOST", "localhost")
    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_PORT", "9000")
    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_DATABASE", "probalytics_test")
    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_USERNAME", "user")
    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_PASSWORD", "secret")
    monkeypatch.setenv("PROBALYTICS_CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("PROBALYTICS_FRAME", "pandas")
    monkeypatch.setattr(ProbalyticsClient, "from_clickhouse", classmethod(fake_from_clickhouse))

    client = ProbalyticsClient.from_env()

    assert client == "client"
    assert captured == {
        "host": "localhost",
        "port": 9000,
        "database": "probalytics_test",
        "username": "user",
        "password": "secret",
        "secure": False,
        "frame": "pandas",
    }


def test_client_from_env_reports_missing_credentials(monkeypatch) -> None:
    monkeypatch.delenv("PROBALYTICS_CLICKHOUSE_USERNAME", raising=False)
    monkeypatch.delenv("PROBALYTICS_CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("PROBALYTICS_CLICKHOUSE_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="PROBALYTICS_CLICKHOUSE_USERNAME"):
        ProbalyticsClient.from_env()


def test_markets_supports_array_filters() -> None:
    client = clickhouse_with_recorder()
    market_ids = [
        UUID("550e8400-e29b-41d4-a716-446655440000"),
        UUID("550e8400-e29b-41d4-a716-446655440002"),
    ]

    client.markets(
        market_id=market_ids,
        market_platform_id=["0xmarket", "0xother"],
        platform=["POLYMARKET", "KALSHI"],
        status=["ACTIVE", "PAUSED"],
    )

    assert "id IN %(market_id)s" in client.client.query
    assert "platform_id IN %(market_platform_id)s" in client.client.query
    assert "platform IN %(platform)s" in client.client.query
    assert "status IN %(status)s" in client.client.query
    assert client.client.params["market_id"] == tuple(str(value) for value in market_ids)
    assert client.client.params["market_platform_id"] == ("0xmarket", "0xother")
    assert client.client.params["platform"] == ("POLYMARKET", "KALSHI")
    assert client.client.params["status"] == ("ACTIVE", "PAUSED")


def test_markets_keeps_scalar_market_filters_as_equals() -> None:
    client = clickhouse_with_recorder()
    market_id = UUID("550e8400-e29b-41d4-a716-446655440000")

    client.markets(market_id=market_id, market_platform_id="0xmarket", platform="POLYMARKET")

    assert "id = %(market_id)s" in client.client.query
    assert "platform_id = %(market_platform_id)s" in client.client.query
    assert "platform = %(platform)s" in client.client.query
    assert client.client.params["market_id"] == str(market_id)
    assert client.client.params["market_platform_id"] == "0xmarket"
    assert client.client.params["platform"] == "POLYMARKET"


def test_fills_supports_array_filters() -> None:
    client = clickhouse_with_recorder()
    market_ids = [
        UUID("550e8400-e29b-41d4-a716-446655440000"),
        UUID("550e8400-e29b-41d4-a716-446655440002"),
    ]

    client.fills(
        market_id=market_ids,
        market_platform_id=["0xmarket", "0xother"],
        platform=["POLYMARKET", "KALSHI"],
        taker_side=["BUY", "SELL"],
        trader_id=["trader-a", "trader-b"],
    )

    assert "market_id IN %(market_id)s" in client.client.query
    assert "market_platform_id IN %(market_platform_id)s" in client.client.query
    assert "platform IN %(platform)s" in client.client.query
    assert "taker_side IN %(taker_side)s" in client.client.query
    assert "(taker_id IN %(trader_id)s OR maker_id IN %(trader_id)s)" in client.client.query
    assert client.client.params["market_id"] == tuple(str(value) for value in market_ids)
    assert client.client.params["market_platform_id"] == ("0xmarket", "0xother")
    assert client.client.params["platform"] == ("POLYMARKET", "KALSHI")
    assert client.client.params["taker_side"] == ("BUY", "SELL")
    assert client.client.params["trader_id"] == ("trader-a", "trader-b")


def test_fills_keeps_scalar_filters_as_equals() -> None:
    client = clickhouse_with_recorder()

    client.fills(market_platform_id="0xmarket", platform="POLYMARKET")

    assert "market_platform_id = %(market_platform_id)s" in client.client.query
    assert "platform = %(platform)s" in client.client.query
    assert client.client.params["market_platform_id"] == "0xmarket"
    assert client.client.params["platform"] == "POLYMARKET"


def test_fills_selects_provenance_and_metadata() -> None:
    client = clickhouse_with_recorder()

    client.fills(limit=10)

    assert "source_block_number, source_tx_hash, source_log_index" in client.client.query
    assert "timestamp, indexed_at, toJSONString(metadata) AS metadata" in client.client.query


def test_fill_row_decodes_json_metadata() -> None:
    row = {
        "outcome": {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "platform_id": "yes",
            "name": "Yes",
            "index": 0,
        },
        "metadata": '{"instrument":"BTC","liquidation":false}',
    }

    assert _fill_row(row)["metadata"] == {"instrument": "BTC", "liquidation": False}


def test_orderbook_snapshots_select_quality_fields_and_filters() -> None:
    client = clickhouse_with_recorder()

    client.orderbook_snapshots(
        start_time="2026-03-15T00:00:00Z",
        end_time="2026-03-15T00:01:00Z",
        state=["VERIFIED", "INTERMEDIATE"],
        continuity="RESET",
        limit=10,
    )

    assert "indexed_at, hash, state, continuity, path_index" in client.client.query
    assert "state IN %(state)s" in client.client.query
    assert "continuity = %(continuity)s" in client.client.query
    assert "ORDER BY timestamp ASC, path_index ASC, indexed_at ASC" in client.client.query
    assert client.client.params["state"] == ("VERIFIED", "INTERMEDIATE")
    assert client.client.params["continuity"] == "RESET"


def test_clickhouse_rejects_invalid_limits() -> None:
    client = clickhouse_with_recorder()

    with pytest.raises(ValueError, match="limit must be at least 1"):
        client.markets(limit=0)

    with pytest.raises(ValueError, match="max_rows must be at least 1"):
        client.fills(max_rows=0)


def clickhouse_with_recorder() -> ClickHouseClient:
    client = ClickHouseClient.__new__(ClickHouseClient)
    client.client = Recorder()
    return client


class Recorder:
    def execute(self, query, params=None, **kwargs):
        self.query = query
        self.params = params or {}
        return [], []
