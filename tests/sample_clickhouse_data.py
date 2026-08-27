from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from clickhouse_driver import Client as DriverClient

DATABASE = "probalytics"
PASSWORD = "probalytics-test"

MARKET_A = UUID("550e8400-e29b-41d4-a716-446655440000")
MARKET_B = UUID("550e8400-e29b-41d4-a716-446655440002")
OUTCOME_A = UUID("550e8400-e29b-41d4-a716-446655440001")
OUTCOME_B = UUID("550e8400-e29b-41d4-a716-446655440003")
FILL_A = UUID("650e8400-e29b-41d4-a716-446655440000")
FILL_B = UUID("650e8400-e29b-41d4-a716-446655440001")

SAMPLE_TIME = datetime(2026, 3, 15, tzinfo=timezone.utc)
SAMPLE_TX_HASH = "0x" + "0" * 64

MARKET_COLUMNS = (
    "id",
    "platform",
    "platform_id",
    "slug",
    "url",
    "title",
    "description",
    "category",
    "tags",
    "market_type",
    "outcomes",
    "created_at",
    "opened_at",
    "closes_at",
    "resolves_at",
    "end_date",
    "reset_at",
    "resolution_type",
    "resolution_winning_outcome_id",
    "resolution_outcome_payouts",
    "resolution_resolved_by",
    "resolution_resolved_at",
    "resolution_source_block_number",
    "resolution_source_tx_hash",
    "status",
    "source_block_number",
    "source_tx_hash",
    "indexed_at",
)

FILL_COLUMNS = (
    "id",
    "market_id",
    "market_platform_id",
    "platform",
    "platform_id",
    "outcome",
    "size",
    "price",
    "normalized_price",
    "taker_side",
    "taker_cash_flow",
    "maker_cash_flow",
    "taker_id",
    "maker_id",
    "fee",
    "source_block_number",
    "source_tx_hash",
    "source_log_index",
    "timestamp",
    "indexed_at",
)

ORDERBOOK_SNAPSHOT_COLUMNS = (
    "market_id",
    "market_platform_id",
    "platform",
    "outcome",
    "bids",
    "asks",
    "timestamp",
    "indexed_at",
    "hash",
    "state",
    "continuity",
    "path_index",
)

MARKET_ROWS = [
    (
        MARKET_A,
        "POLYMARKET",
        "0xmarket",
        "market-a",
        "https://example.com/a",
        "Market A",
        "Sample Polymarket market",
        "Politics",
        ["tag-a", "binary"],
        "BINARY",
        [(OUTCOME_A, "yes", "Yes", 0)],
        SAMPLE_TIME,
        SAMPLE_TIME,
        None,
        None,
        None,
        None,
        None,
        None,
        [],
        None,
        None,
        None,
        None,
        "ACTIVE",
        1,
        SAMPLE_TX_HASH,
        SAMPLE_TIME,
    ),
    (
        MARKET_B,
        "KALSHI",
        "KXBTC-26JUN-T50000",
        "market-b",
        "https://example.com/b",
        "Market B",
        "Sample Kalshi market",
        "Crypto",
        ["tag-b", "binary"],
        "BINARY",
        [(OUTCOME_B, "yes", "Yes", 0)],
        SAMPLE_TIME.replace(hour=1),
        SAMPLE_TIME.replace(hour=1),
        None,
        None,
        None,
        None,
        None,
        None,
        [],
        None,
        None,
        None,
        None,
        "PAUSED",
        1,
        SAMPLE_TX_HASH,
        SAMPLE_TIME.replace(hour=1),
    ),
]

FILL_ROWS = [
    (
        FILL_A,
        MARKET_A,
        "0xmarket",
        "POLYMARKET",
        "fill-a",
        (OUTCOME_A, "yes", "Yes", 0),
        Decimal("10"),
        Decimal("0.45"),
        Decimal("0.45"),
        "BUY",
        Decimal("4.5"),
        Decimal("4.5"),
        "trader-a",
        "maker-a",
        Decimal("0"),
        None,
        None,
        None,
        SAMPLE_TIME.replace(second=1),
        SAMPLE_TIME.replace(second=1),
    ),
    (
        FILL_B,
        MARKET_B,
        "KXBTC-26JUN-T50000",
        "KALSHI",
        "fill-b",
        (OUTCOME_B, "yes", "Yes", 0),
        Decimal("5"),
        Decimal("0.60"),
        Decimal("0.60"),
        "SELL",
        Decimal("3"),
        Decimal("3"),
        "trader-b",
        "maker-b",
        Decimal("0"),
        None,
        None,
        None,
        SAMPLE_TIME.replace(second=2),
        SAMPLE_TIME.replace(second=2),
    ),
]

ORDERBOOK_SNAPSHOT_ROWS = [
    (
        MARKET_A,
        "0xmarket",
        "POLYMARKET",
        (OUTCOME_A, "yes", "Yes", 0),
        [(Decimal("0.44"), Decimal("10"))],
        [(Decimal("0.46"), Decimal("8"))],
        SAMPLE_TIME.replace(second=1),
        SAMPLE_TIME.replace(second=1),
        101,
        "VERIFIED",
        "RESET",
        0,
    ),
    (
        MARKET_B,
        "KXBTC-26JUN-T50000",
        "KALSHI",
        (OUTCOME_B, "yes", "Yes", 0),
        [(Decimal("0.59"), Decimal("5"))],
        [(Decimal("0.61"), Decimal("6"))],
        SAMPLE_TIME.replace(second=2),
        SAMPLE_TIME.replace(second=2),
        202,
        "VERIFIED",
        "CONTIGUOUS",
        0,
    ),
]


def create_schema(client: DriverClient) -> None:
    for query in (CREATE_MARKETS, CREATE_FILLS, CREATE_ORDERBOOK_SNAPSHOTS):
        client.execute(query)


def seed_sample_data(client: DriverClient) -> None:
    insert_rows(client, "markets", MARKET_COLUMNS, MARKET_ROWS)
    insert_rows(client, "fills", FILL_COLUMNS, FILL_ROWS)
    insert_rows(client, "orderbook_snapshots", ORDERBOOK_SNAPSHOT_COLUMNS, ORDERBOOK_SNAPSHOT_ROWS)


def insert_rows(client: DriverClient, table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
    column_list = ", ".join(columns)
    client.execute(f"INSERT INTO {table} ({column_list}) VALUES", rows)


CREATE_MARKETS = """
CREATE TABLE markets (
    id UUID,
    platform Enum('POLYMARKET', 'KALSHI'),
    platform_id String,
    slug String,
    url String,
    title String,
    description String,
    category LowCardinality(String),
    tags Array(LowCardinality(String)),
    market_type Enum('BINARY', 'MULTIPLE', 'SCALAR', 'PARLAY', 'PERPETUAL'),
    outcomes Array(Tuple(id UUID, platform_id String, name String, index UInt8)),
    created_at DateTime64(3),
    opened_at Nullable(DateTime64(3)),
    closes_at Nullable(DateTime64(3)),
    resolves_at Nullable(DateTime64(3)),
    end_date Nullable(DateTime64(3)),
    reset_at Nullable(DateTime64(3)),
    resolution_type Nullable(Enum('STANDARD', 'SPLIT', 'VOID')),
    resolution_winning_outcome_id Nullable(UUID),
    resolution_outcome_payouts Array(Tuple(outcome_id UUID, payout Decimal128(18))),
    resolution_resolved_by Nullable(String),
    resolution_resolved_at Nullable(DateTime64(3)),
    resolution_source_block_number Nullable(UInt64),
    resolution_source_tx_hash Nullable(String),
    status Enum('PENDING', 'ACTIVE', 'PAUSED', 'CLOSED', 'RESOLVED'),
    source_block_number UInt64,
    source_tx_hash FixedString(66),
    indexed_at DateTime64(3)
) ENGINE = ReplacingMergeTree(indexed_at)
ORDER BY (platform, created_at, id, platform_id)
"""

CREATE_FILLS = """
CREATE TABLE fills (
    id UUID,
    market_id UUID,
    market_platform_id String,
    platform Enum('POLYMARKET', 'KALSHI'),
    platform_id String,
    outcome Tuple(id UUID, platform_id String, name String, index UInt8),
    size Decimal128(18),
    price Decimal128(18),
    normalized_price Decimal128(18),
    taker_side Enum('BUY', 'SELL'),
    taker_cash_flow Decimal128(18),
    maker_cash_flow Decimal128(18),
    taker_id Nullable(String),
    maker_id Nullable(String),
    fee Decimal128(18),
    source_block_number Nullable(UInt64),
    source_tx_hash Nullable(String),
    source_log_index Nullable(UInt32),
    timestamp DateTime64(6),
    indexed_at DateTime64(9),
    metadata JSON DEFAULT '{}'
) ENGINE = ReplacingMergeTree(indexed_at)
ORDER BY (platform, market_id, timestamp, id)
PARTITION BY toYYYYMM(timestamp)
"""

CREATE_ORDERBOOK_SNAPSHOTS = """
CREATE TABLE orderbook_snapshots (
    market_id UUID,
    market_platform_id String,
    platform Enum('POLYMARKET', 'KALSHI'),
    outcome Tuple(id UUID, platform_id String, name String, index UInt8),
    bids Array(Tuple(price Decimal64(6), size Decimal64(6))),
    asks Array(Tuple(price Decimal64(6), size Decimal64(6))),
    timestamp DateTime64(9),
    indexed_at DateTime64(9),
    hash UInt64,
    state Enum8('VERIFIED' = 1, 'INTERMEDIATE' = 2),
    continuity Enum8('CONTIGUOUS' = 1, 'RESET' = 2),
    path_index UInt32
) ENGINE = ReplacingMergeTree(indexed_at)
ORDER BY (market_id, outcome.id, timestamp, hash, state, continuity, path_index)
PARTITION BY toYYYYMM(timestamp)
"""
