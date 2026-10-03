from __future__ import annotations

import os
import time

import pandas as pd
import polars as pl
import pytest
from clickhouse_driver import Client as DriverClient

from probalytics import ProbalyticsClient
from sample_clickhouse_data import (
    DATABASE,
    FILL_ROWS,
    MARKET_A,
    MARKET_B,
    MARKET_ROWS,
    ORDERBOOK_SNAPSHOT_ROWS,
    PASSWORD,
    create_schema,
    seed_sample_data,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def clickhouse_config():
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

    from testcontainers.core.container import DockerContainer

    container = (
        DockerContainer("clickhouse/clickhouse-server:25.8-alpine")
        .with_env("CLICKHOUSE_DB", DATABASE)
        .with_env("CLICKHOUSE_USER", "default")
        .with_env("CLICKHOUSE_PASSWORD", PASSWORD)
        .with_exposed_ports(9000)
    )
    container.start()
    try:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(9000))
        driver = wait_for_clickhouse(host, port)
        create_schema(driver)
        seed_sample_data(driver)
        yield {"host": host, "port": port}
    finally:
        container.stop()


@pytest.fixture()
def client(clickhouse_config) -> ProbalyticsClient:
    return ProbalyticsClient.from_clickhouse(
        host=clickhouse_config["host"],
        port=clickhouse_config["port"],
        username="default",
        password=PASSWORD,
        database=DATABASE,
        secure=False,
        compression=False,
        frame="pandas",
    )


def test_sample_data_matches_production_shapes(client: ProbalyticsClient) -> None:
    counts = client.query(
        """
        SELECT 'markets' AS table_name, count() AS rows FROM markets
        UNION ALL
        SELECT 'fills' AS table_name, count() AS rows FROM fills
        UNION ALL
        SELECT 'orderbook_snapshots' AS table_name, count() AS rows FROM orderbook_snapshots
        ORDER BY table_name
        """
    )

    assert dict(zip(counts["table_name"], counts["rows"], strict=True)) == {
        "fills": len(FILL_ROWS),
        "markets": len(MARKET_ROWS),
        "orderbook_snapshots": len(ORDERBOOK_SNAPSHOT_ROWS),
    }


def test_markets_filters_accept_arrays_against_clickhouse(client: ProbalyticsClient) -> None:
    markets = client.markets(
        market_id=[MARKET_A, MARKET_B],
        market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
        platform=["POLYMARKET", "KALSHI"],
        status=["ACTIVE", "PAUSED"],
        limit=10,
    )

    assert {market.id for market in markets} == {MARKET_A, MARKET_B}
    assert {market.platform_id for market in markets} == {"0xmarket", "KXBTC-26JUN-T50000"}


def test_markets_frame_reads_sample_data(client: ProbalyticsClient) -> None:
    markets = client.markets_frame(
        market_id=[MARKET_A, MARKET_B],
        market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
        platform=["POLYMARKET", "KALSHI"],
        status=["ACTIVE", "PAUSED"],
    )

    assert isinstance(markets, pd.DataFrame)
    assert set(markets["platform_id"]) == {"0xmarket", "KXBTC-26JUN-T50000"}
    assert set(markets["status"]) == {"ACTIVE", "PAUSED"}


def test_fills_models_accept_full_market_and_array_filters(client: ProbalyticsClient) -> None:
    market = client.markets(platform="POLYMARKET", status="ACTIVE", limit=1)[0]

    fills_for_market = client.fills_models(market=market)
    fills_from_market = market.fills_models()
    fills_for_arrays = client.fills_models(
        platform=["POLYMARKET", "KALSHI"],
        market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
        taker_side=["BUY", "SELL"],
        trader_id=["trader-a", "trader-b"],
        limit=10,
    )

    assert [fill.market_id for fill in fills_for_market] == [MARKET_A]
    assert [fill.market_id for fill in fills_from_market] == [MARKET_A]
    assert {fill.market_id for fill in fills_for_arrays} == {MARKET_A, MARKET_B}
    assert {fill.taker_side for fill in fills_for_arrays} == {"BUY", "SELL"}


def test_fills_dataframe_uses_global_frame_and_market_id_arrays(client: ProbalyticsClient) -> None:
    fills = client.fills(market_id=[MARKET_A, MARKET_B], limit=10)

    assert isinstance(fills, pd.DataFrame)
    assert set(fills["market_platform_id"]) == {"0xmarket", "KXBTC-26JUN-T50000"}
    assert set(fills["platform"]) == {"POLYMARKET", "KALSHI"}
    assert all(value == {} for value in fills["metadata"])
    assert isinstance(fills.loc[0, "outcome"], dict)
    assert set(fills.loc[0, "outcome"]) == {"id", "platform_id", "name", "index"}
    assert isinstance(fills.loc[0, "outcome"]["id"], str)


def test_fills_polars_dataframe_uses_struct_columns(client: ProbalyticsClient) -> None:
    fills = client.fills(market_id=[MARKET_A, MARKET_B], limit=10, frame="polars")

    assert isinstance(fills, pl.DataFrame)
    assert isinstance(fills.schema["outcome"], pl.Struct)
    assert set(fills["outcome"].struct.field("name").to_list()) == {"Yes"}
    assert all(isinstance(value, str) for value in fills["outcome"].struct.field("id").to_list())


def test_market_convenience_methods_query_related_data(client: ProbalyticsClient) -> None:
    market = client.markets(platform="POLYMARKET", status="ACTIVE", limit=1)[0]

    fills = market.fills(limit=10)
    snapshots = market.orderbook_snapshots(
        start_time="2026-03-15T00:00:00Z",
        end_time="2026-03-15T00:02:00Z",
        limit=10,
    )

    assert isinstance(fills, pd.DataFrame)
    assert set(fills["market_id"]) == {MARKET_A}
    assert isinstance(snapshots, pd.DataFrame)
    assert set(snapshots["market_id"]) == {MARKET_A}


def test_orderbook_snapshots_accept_market_platform_id_arrays(client: ProbalyticsClient) -> None:
    snapshots = client.orderbook_snapshots(
        start_time="2026-03-15T00:00:00Z",
        end_time="2026-03-15T00:02:00Z",
        platform=["POLYMARKET", "KALSHI"],
        market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
        state="VERIFIED",
        continuity=["RESET", "CONTIGUOUS"],
        limit=10,
    )

    assert isinstance(snapshots, pd.DataFrame)
    assert set(snapshots["market_platform_id"]) == {"0xmarket", "KXBTC-26JUN-T50000"}
    assert isinstance(snapshots.loc[0, "outcome"], dict)
    assert isinstance(snapshots.loc[0, "outcome"]["id"], str)
    assert isinstance(snapshots.loc[0, "bids"], list)
    assert isinstance(snapshots.loc[0, "bids"][0], dict)
    assert set(snapshots["state"]) == {"VERIFIED"}
    assert set(snapshots["continuity"]) == {"RESET", "CONTIGUOUS"}
    assert set(snapshots.columns) >= {"indexed_at", "hash", "state", "continuity", "path_index"}


def wait_for_clickhouse(host: str, port: int) -> DriverClient:
    deadline = time.time() + 60
    last_error = None
    while time.time() < deadline:
        try:
            client = DriverClient(
                host=host,
                port=port,
                user="default",
                password=PASSWORD,
                database=DATABASE,
                compression=False,
            )
            client.execute("SELECT 1")
            return client
        except Exception as error:
            last_error = error
            time.sleep(1)
    raise RuntimeError(f"ClickHouse did not become ready: {last_error}")
