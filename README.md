# Probalytics Python Client

Python client for Probalytics market data. Use it to query markets, fills, and
orderbook snapshots directly from ClickHouse and return results as Polars or
pandas dataframes.

## Installation

```bash
pip install probalytics
```

The client requires Python 3.11 or newer.

Polars support is included by default. To use `frame="pandas"`, install the
pandas extra:

```bash
pip install "probalytics[pandas]"
```

## Connect

```python
from probalytics import ProbalyticsClient

client = ProbalyticsClient.from_clickhouse(
    host="clickhouse.probalytics.io",
    username="your_username",
    password="your_password",
)
```

By default, the client connects securely to the `probalytics` database. If your
account uses a custom host, port, or database, pass those values when creating
the client.

```python
client = ProbalyticsClient.from_clickhouse(
    host="clickhouse.probalytics.io",
    port=9440,
    database="probalytics",
    username="your_username",
    password="your_password",
    secure=True,
    frame="polars",
)
```

You can also configure the client from environment variables:

```bash
export PROBALYTICS_CLICKHOUSE_USERNAME="your_username"
export PROBALYTICS_CLICKHOUSE_PASSWORD="your_password"
export PROBALYTICS_CLICKHOUSE_HOST="clickhouse.probalytics.io"
export PROBALYTICS_FRAME="pandas"
```

```python
client = ProbalyticsClient.from_env()
```

Use the client as a context manager when you want the connection closed
automatically:

```python
with ProbalyticsClient.from_env() as client:
    markets = client.markets(platform="POLYMARKET", status="ACTIVE")
```

## Query Markets

Markets are returned as typed Pydantic models.

```python
markets = client.markets(
    market_platform_id="0xmarket",
    platform="POLYMARKET",
    status="ACTIVE",
    limit=100,
)

market = markets[0]
print(market.title)
print(market.platform)
print(market.platform_id)
```

You can also return markets as a dataframe.

```python
markets_df = client.markets_frame(
    platform="KALSHI",
    status="ACTIVE",
    frame="polars",
)
```

Filters such as `platform` and `status` accept either one value or a list of
values.

```python
markets = client.markets(
    market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
    platform=["POLYMARKET", "KALSHI"],
    status=["ACTIVE", "PAUSED"],
)
```

## Query Fills

Fills return as a Polars dataframe by default.

```python
fills = client.fills(
    market=market,
    start_time="2026-03-15T00:00:00Z",
    end_time="2026-03-16T00:00:00Z",
)
```

Use `market`, `market_id`, or `market_platform_id` to scope fills to one or more
markets. A full market object is the most convenient option when you already
loaded markets first.

```python
fills = client.fills(market=market)
fills = market.fills()
fills = client.fills(market_id=market.id)
fills = client.fills(market_platform_id=market.platform_id, platform=market.platform)
```

`market_id`, `market_platform_id`, `platform`, `taker_side`, and `trader_id`
also accept lists.

```python
fills = client.fills(
    platform=["POLYMARKET", "KALSHI"],
    market_platform_id=["0xmarket", "KXBTC-26JUN-T50000"],
    taker_side=["BUY", "SELL"],
    start_time="2026-03-15T00:00:00Z",
)
```

Use a market selector or a bounded time range when querying fills. This keeps
queries fast and avoids scanning more data than you need.

`start_time` / `end_time` filter `timestamp` (the exchange time) on `fills` and
`orderbook_snapshots`, and `created_at` on `markets` — a market created months
ago still returns today's fills.

Filter by participant or taker side:

```python
fills = client.fills(
    market=market,
    trader_id="0x1234...",
    taker_side="BUY",
    start_time="2026-03-15T00:00:00Z",
)
```

If you need typed fill models instead of a dataframe:

```python
fill_models = client.fills_models(
    market=market,
    start_time="2026-03-15T00:00:00Z",
)

fill_models = market.fills_models(
    start_time="2026-03-15T00:00:00Z",
)
```

## Query Orderbook Snapshots

Orderbook snapshots are available for accounts with orderbook access.

```python
book = client.orderbook_snapshots(
    market=market,
    start_time="2026-03-15T00:00:00Z",
    end_time="2026-03-15T00:01:00Z",
)

book = market.orderbook_snapshots(
    start_time="2026-03-15T00:00:00Z",
    end_time="2026-03-15T00:01:00Z",
)
```

Each snapshot is a complete replacement book for one outcome. Rows include
`indexed_at`, `hash`, `state`, `continuity`, and `path_index` in addition to the
market identifiers, outcome, bids, asks, and source timestamp.

`state` is `VERIFIED` or `INTERMEDIATE`. `continuity` is `CONTIGUOUS` (the
transition from the previous book was provable), `RESET` (it was not — the first
state of a book is deliberately `RESET`), or `UNKNOWN` for rows predating
continuity tracking. Several distinct states can share one millisecond; `hash`
separates them and `path_index` orders them within a recovered path.

Note that these columns were added to the warehouse in August 2026. Rows written
before then read the column default rather than a measured value: `hash` is 0
before 2026-08-02, `state` reads `VERIFIED` before 2026-08-21, and `continuity`
reads `UNKNOWN` before 2026-08-22.

## Choose Polars or pandas

All dataframe methods return Polars by default. Set `frame="pandas"` when
creating the client to use pandas globally. pandas support is optional; install
it with `pip install "probalytics[pandas]"`.

```python
client = ProbalyticsClient.from_clickhouse(
    host="clickhouse.probalytics.io",
    username="your_username",
    password="your_password",
    frame="pandas",
)
```

You can also override the frame for a single call.

```python
fills_pd = client.fills(
    market=market,
    start_time="2026-03-15T00:00:00Z",
    frame="pandas",
)
```

Invalid frame values fail early with a clear error. Supported values are
`"polars"` and `"pandas"`.

## Run Custom SQL

Use `query()` for read-only ClickHouse queries when the convenience methods do
not cover your use case.

```python
from datetime import datetime, timezone

df = client.query(
    """
    SELECT platform, count() AS fills
    FROM fills
    WHERE timestamp >= %(start_time)s
    GROUP BY platform
    ORDER BY fills DESC
    """,
    parameters={"start_time": datetime(2026, 3, 15, tzinfo=timezone.utc)},
)
```

Always pass user-provided values through `parameters` instead of formatting them
directly into SQL strings.

Unlike the convenience methods, `query()` passes parameters straight to
ClickHouse — it does not parse date strings for you. Pass a `datetime`, or a
string ClickHouse accepts such as `"2026-03-15 00:00:00"`. An ISO string with a
trailing `Z` is rejected by the server.

## Supported Filters

Every method returns at most `limit` rows, and **`limit` defaults to 1000**.
Raise it explicitly when you want more than that — results are truncated
silently, not flagged.

`markets()` and `markets_frame()` support:

- `start_time`
- `end_time`
- `status` or list of statuses
- `platform` or list of platforms
- `market_id` or list of market IDs
- `market_platform_id` or list of market platform IDs
- `limit`
- `max_rows`

`fills()` and `fills_models()` support:

- `start_time`
- `end_time`
- `platform` or list of platforms
- `market`
- `market_id` or list of market IDs
- `market_platform_id` or list of market platform IDs
- `taker_side` or list of taker sides
- `trader_id` or list of trader IDs
- `limit`
- `max_rows`

`orderbook_snapshots()` supports:

- `start_time` (**required**)
- `end_time` (**required**)
- `platform` or list of platforms
- `market`
- `market_id` or list of market IDs
- `market_platform_id` or list of market platform IDs
- `state` or list of states
- `continuity` or list of continuity values
- `limit`

## Local Development

```bash
uv sync --extra test
uv run --extra test pytest
```

Run the ClickHouse integration tests with Docker:

```bash
PROBALYTICS_RUN_INTEGRATION=1 uv run --extra test pytest tests/test_clickhouse_integration.py
```

Use `PYTHONPATH=src` if running tests without installing the package into the
active environment.
