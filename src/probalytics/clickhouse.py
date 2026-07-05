from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from probalytics._frames import FrameKind, dataframe_to_frame, normalize_time, validate_frame
from probalytics._filters import IDFilter, StringFilter, market_filter
from probalytics.models import Fill, Market

OUTCOME_FRAME_EXPR = (
    "CAST((toString(outcome.id), outcome.platform_id, outcome.name, outcome.index), "
    "'Tuple(id String, platform_id String, name String, index UInt8)')"
)
OUTCOMES_FRAME_EXPR = (
    "arrayMap(outcome -> "
    "CAST((toString(outcome.id), outcome.platform_id, outcome.name, outcome.index), "
    "'Tuple(id String, platform_id String, name String, index UInt8)'), outcomes)"
)
RESOLUTION_PAYOUTS_FRAME_EXPR = (
    "arrayMap(payout -> "
    "CAST((toString(payout.outcome_id), payout.payout), "
    "'Tuple(outcome_id String, payout Decimal128(18))'), resolution_outcome_payouts)"
)


class ClickHouseClient:
    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        database: str = "probalytics",
        secure: bool = True,
        port: int | None = None,
        compression: bool | str = "lz4",
        tcp_keepalive: bool | tuple[int, int, int] = True,
        **kwargs: Any,
    ) -> None:
        from clickhouse_driver import Client

        settings = kwargs.pop("settings", {}).copy()
        settings.setdefault("allow_experimental_object_type", 1)
        settings.setdefault("namedtuple_as_json", True)
        client_kwargs = {
            "host": host,
            "user": username,
            "password": password,
            "database": database,
            "secure": secure,
            "compression": compression,
            "tcp_keepalive": tcp_keepalive,
            "settings": settings,
            **kwargs,
        }
        if port is not None:
            client_kwargs["port"] = port
        self.client = Client(**client_kwargs)

    def close(self) -> None:
        self.client.disconnect()

    def __enter__(self) -> "ClickHouseClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def query(
        self,
        sql: str,
        *,
        parameters: dict[str, Any] | None = None,
        frame: FrameKind = "polars",
    ) -> Any:
        return self._query_frame(
            sql,
            parameters or {},
            validate_frame(frame),
        )

    def markets(
        self,
        *,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        status: StringFilter = None,
        platform: StringFilter = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        limit: int = 1000,
        max_rows: int | None = None,
    ) -> list[Market]:
        limit = _limit(limit, max_rows)
        where, params = _where(
            [
                ("created_at >= %(start_time)s", "start_time", normalize_time(start_time)),
                ("created_at <= %(end_time)s", "end_time", normalize_time(end_time)),
                _filter("status", "status", status),
                _filter("platform", "platform", platform),
                _filter("id", "market_id", market_id),
                _filter("platform_id", "market_platform_id", market_platform_id),
            ]
        )
        params["limit"] = limit
        query = f"""
            SELECT *
            FROM markets FINAL
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT %(limit)s
        """
        return [Market.model_validate(_market_row(row)) for row in self._json_rows(query, params)]

    def markets_frame(self, *, frame: FrameKind = "polars", **filters: Any) -> Any:
        return self._markets_arrow(frame=frame, **filters)

    def fills(
        self,
        *,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        platform: StringFilter = None,
        market: Market | str | UUID | None = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        taker_side: StringFilter = None,
        trader_id: StringFilter = None,
        limit: int = 1000,
        max_rows: int | None = None,
    ) -> list[Fill]:
        limit = _limit(limit, max_rows)
        market_id, market_platform_id, platform = market_filter(market, market_id, market_platform_id, platform)
        where, params = _where(
            [
                ("timestamp >= %(start_time)s", "start_time", normalize_time(start_time)),
                ("timestamp <= %(end_time)s", "end_time", normalize_time(end_time)),
                _filter("platform", "platform", platform),
                _filter("market_id", "market_id", market_id),
                _filter("market_platform_id", "market_platform_id", market_platform_id),
                _filter("taker_side", "taker_side", taker_side),
                _filter(
                    "trader_id",
                    "trader_id",
                    trader_id,
                    eq_sql="(taker_id = %(trader_id)s OR maker_id = %(trader_id)s)",
                    in_sql="(taker_id IN %(trader_id)s OR maker_id IN %(trader_id)s)",
                ),
            ]
        )
        params["limit"] = limit
        query = f"""
            SELECT
                id, market_id, market_platform_id, platform, platform_id, outcome,
                size, price, normalized_price, taker_side, taker_cash_flow,
                maker_cash_flow, taker_id, maker_id, fee, timestamp
            FROM fills
            {where}
            ORDER BY timestamp ASC, id ASC
            LIMIT %(limit)s
        """
        return [Fill.model_validate(_fill_row(row)) for row in self._json_rows(query, params)]

    def fills_frame(self, *, frame: FrameKind = "polars", **filters: Any) -> Any:
        return self._fills_arrow(frame=frame, **filters)

    def orderbook_snapshots(
        self,
        *,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        platform: StringFilter = None,
        market: Market | str | UUID | None = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        limit: int = 1000,
        frame: FrameKind = "polars",
    ) -> Any:
        limit = _limit(limit, None)
        market_id, market_platform_id, platform = market_filter(market, market_id, market_platform_id, platform)
        where, params = _where(
            [
                ("timestamp >= %(start_time)s", "start_time", normalize_time(start_time)),
                ("timestamp <= %(end_time)s", "end_time", normalize_time(end_time)),
                _filter("platform", "platform", platform),
                _filter("market_id", "market_id", market_id),
                _filter("market_platform_id", "market_platform_id", market_platform_id),
            ]
        )
        params["limit"] = limit
        query = f"""
            SELECT
                market_id, market_platform_id, platform,
                {OUTCOME_FRAME_EXPR} AS outcome,
                bids, asks, timestamp
            FROM orderbook_snapshots
            {where}
            ORDER BY timestamp ASC
            LIMIT %(limit)s
        """
        return self._query_frame(query, params, frame)

    def _markets_arrow(
        self,
        *,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        status: StringFilter = None,
        platform: StringFilter = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        limit: int = 1000,
        max_rows: int | None = None,
        frame: FrameKind = "polars",
    ) -> Any:
        limit = _limit(limit, max_rows)
        where, params = _where(
            [
                ("created_at >= %(start_time)s", "start_time", normalize_time(start_time)),
                ("created_at <= %(end_time)s", "end_time", normalize_time(end_time)),
                _filter("status", "status", status),
                _filter("platform", "platform", platform),
                _filter("id", "market_id", market_id),
                _filter("platform_id", "market_platform_id", market_platform_id),
            ]
        )
        params["limit"] = limit
        query = f"""
            SELECT
                id, platform, platform_id, slug, url, title, description,
                category, tags, market_type, {OUTCOMES_FRAME_EXPR} AS outcomes,
                created_at, opened_at, closes_at, resolves_at, end_date, reset_at,
                resolution_type, resolution_winning_outcome_id,
                {RESOLUTION_PAYOUTS_FRAME_EXPR} AS resolution_outcome_payouts,
                resolution_resolved_by, resolution_resolved_at,
                resolution_source_block_number, resolution_source_tx_hash,
                status, source_block_number, source_tx_hash, indexed_at
            FROM markets FINAL
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT %(limit)s
        """
        return self._query_frame(query, params, frame)

    def _fills_arrow(
        self,
        *,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        platform: StringFilter = None,
        market: Market | str | UUID | None = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        taker_side: StringFilter = None,
        trader_id: StringFilter = None,
        limit: int = 1000,
        max_rows: int | None = None,
        frame: FrameKind = "polars",
    ) -> Any:
        limit = _limit(limit, max_rows)
        market_id, market_platform_id, platform = market_filter(market, market_id, market_platform_id, platform)
        where, params = _where(
            [
                ("timestamp >= %(start_time)s", "start_time", normalize_time(start_time)),
                ("timestamp <= %(end_time)s", "end_time", normalize_time(end_time)),
                _filter("platform", "platform", platform),
                _filter("market_id", "market_id", market_id),
                _filter("market_platform_id", "market_platform_id", market_platform_id),
                _filter("taker_side", "taker_side", taker_side),
                _filter(
                    "trader_id",
                    "trader_id",
                    trader_id,
                    eq_sql="(taker_id = %(trader_id)s OR maker_id = %(trader_id)s)",
                    in_sql="(taker_id IN %(trader_id)s OR maker_id IN %(trader_id)s)",
                ),
            ]
        )
        params["limit"] = limit
        query = f"""
            SELECT
                id, market_id, market_platform_id, platform, platform_id,
                {OUTCOME_FRAME_EXPR} AS outcome,
                size, price, normalized_price, taker_side, taker_cash_flow,
                maker_cash_flow, taker_id, maker_id, fee, timestamp
            FROM fills
            {where}
            ORDER BY timestamp ASC, id ASC
            LIMIT %(limit)s
        """
        return self._query_frame(query, params, frame)

    def _json_rows(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        rows, columns = self.client.execute(query, params=params, with_column_types=True)
        names = [col[0] for col in columns]
        return [dict(zip(names, row, strict=True)) for row in rows]

    def _query_frame(
        self,
        query: str,
        params: dict[str, Any],
        frame: FrameKind,
    ) -> Any:
        frame = validate_frame(frame)
        columns_data, columns = self.client.execute(
            query,
            params=params,
            with_column_types=True,
            columnar=True,
        )
        data = {column[0]: values for column, values in zip(columns, columns_data, strict=True)}
        return dataframe_to_frame(data, frame)


def _where(parts: list[tuple[str, str, Any]]) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for sql, name, value in parts:
        if value is None or value == "" or value == ():
            continue
        clauses.append(sql)
        params[name] = value
    return ("WHERE " + " AND ".join(clauses) if clauses else ""), params


def _limit(limit: int, max_rows: int | None) -> int:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if max_rows is not None and max_rows < 1:
        raise ValueError("max_rows must be at least 1")
    return min(limit, max_rows) if max_rows is not None else limit


def _filter(
    column: str,
    name: str,
    value: Any,
    *,
    eq_sql: str | None = None,
    in_sql: str | None = None,
) -> tuple[str, str, Any]:
    value = _filter_value(value)
    if isinstance(value, tuple):
        return in_sql or f"{column} IN %({name})s", name, value
    return eq_sql or f"{column} = %({name})s", name, value


def _filter_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    if _is_multi_filter(value):
        values = tuple(_scalar_filter_value(item) for item in value if item is not None and item != "")
        return values or None
    return _scalar_filter_value(value)


def _is_multi_filter(value: Any) -> bool:
    return isinstance(value, Sequence | set | frozenset) and not isinstance(value, str | bytes | bytearray)


def _scalar_filter_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _market_row(row: dict[str, Any]) -> dict[str, Any]:
    resolution = None
    if row.get("resolution_type"):
        resolution = {
            "type": row.get("resolution_type"),
            "winning_outcome_id": row.get("resolution_winning_outcome_id"),
            "outcome_payouts": [_outcome_payout(value) for value in row.get("resolution_outcome_payouts") or []],
            "resolved_by": row.get("resolution_resolved_by") or "",
            "resolved_at": row.get("resolution_resolved_at"),
        }
    return {
        "id": row["id"],
        "platform": row["platform"],
        "platform_id": row["platform_id"],
        "slug": row.get("slug", ""),
        "url": row.get("url", ""),
        "title": row.get("title", ""),
        "description": row.get("description", ""),
        "category": row.get("category", ""),
        "tags": row.get("tags", []),
        "market_type": row.get("market_type", "UNKNOWN"),
        "outcomes": [_outcome(value) for value in row.get("outcomes", [])],
        "status": row["status"],
        "created_at": row["created_at"],
        "opened_at": row.get("opened_at"),
        "closes_at": row.get("closes_at"),
        "resolves_at": row.get("resolves_at"),
        "end_date": row.get("end_date"),
        "reset_at": row.get("reset_at"),
        "resolution": resolution,
    }


def _fill_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "outcome": _outcome(row["outcome"]),
    }


def _outcome(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "id": value.get("id"),
            "platform_id": value.get("platform_id"),
            "name": value.get("name"),
            "index": value.get("index"),
        }
    if hasattr(value, "_asdict"):
        return _outcome(value._asdict())
    return {
        "id": value[0],
        "platform_id": value[1],
        "name": value[2],
        "index": value[3],
    }


def _outcome_payout(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "outcome_id": value.get("outcome_id"),
            "payout": value.get("payout"),
        }
    if hasattr(value, "_asdict"):
        return _outcome_payout(value._asdict())
    return {
        "outcome_id": value[0],
        "payout": value[1],
    }
