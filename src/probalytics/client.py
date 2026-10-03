from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import UUID

from probalytics._frames import FrameKind, validate_frame
from probalytics._filters import IDFilter, StringFilter
from probalytics.clickhouse import ClickHouseClient
from probalytics.models import Market


class ProbalyticsClient:
    def __init__(self, clickhouse: ClickHouseClient, *, frame: FrameKind = "polars") -> None:
        self.clickhouse = clickhouse
        self.frame = validate_frame(frame)

    @classmethod
    def from_clickhouse(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        database: str = "probalytics",
        secure: bool = True,
        port: int | None = None,
        frame: FrameKind = "polars",
        **kwargs: Any,
    ) -> "ProbalyticsClient":
        return cls.from_clickhouse_client(
            ClickHouseClient(
                host=host,
                username=username,
                password=password,
                database=database,
                secure=secure,
                port=port,
                **kwargs,
            ),
            frame=frame,
        )

    @classmethod
    def from_clickhouse_client(
        cls,
        clickhouse: ClickHouseClient,
        *,
        frame: FrameKind = "polars",
    ) -> "ProbalyticsClient":
        return cls(clickhouse, frame=frame)

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str = "PROBALYTICS_CLICKHOUSE_",
        frame: FrameKind | None = None,
        **kwargs: Any,
    ) -> "ProbalyticsClient":
        username = os.getenv(f"{prefix}USERNAME") or os.getenv(f"{prefix}USER")
        password = os.getenv(f"{prefix}PASSWORD")
        missing = [
            name
            for name, value in (
                (f"{prefix}USERNAME", username),
                (f"{prefix}PASSWORD", password),
            )
            if not value
        ]
        if missing:
            raise ValueError("missing required environment variables: " + ", ".join(missing))

        port = os.getenv(f"{prefix}PORT")
        return cls.from_clickhouse(
            host=os.getenv(f"{prefix}HOST", "clickhouse.probalytics.io"),
            port=int(port) if port else None,
            database=os.getenv(f"{prefix}DATABASE", "probalytics"),
            username=username,
            password=password,
            secure=_env_bool(os.getenv(f"{prefix}SECURE"), default=True),
            frame=frame or validate_frame(os.getenv("PROBALYTICS_FRAME", "polars")),
            **kwargs,
        )

    def close(self) -> None:
        self.clickhouse.close()

    def __enter__(self) -> "ProbalyticsClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def query(
        self,
        sql: str,
        *,
        parameters: dict[str, Any] | None = None,
        frame: FrameKind | None = None,
    ) -> Any:
        return self.clickhouse.query(
            sql,
            parameters=parameters,
            frame=validate_frame(frame or self.frame),
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
        markets = self.clickhouse.markets(
            start_time=start_time,
            end_time=end_time,
            status=status,
            platform=platform,
            market_id=market_id,
            market_platform_id=market_platform_id,
            limit=limit,
            max_rows=max_rows,
        )
        return [market._bind_client(self) for market in markets]

    def markets_frame(self, *, frame: FrameKind | None = None, **filters: Any) -> Any:
        return self.clickhouse.markets_frame(frame=validate_frame(frame or self.frame), **filters)

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
        frame: FrameKind | None = None,
    ) -> Any:
        return self.clickhouse.fills_frame(
            frame=validate_frame(frame or self.frame),
            start_time=start_time,
            end_time=end_time,
            platform=platform,
            market=market,
            market_id=market_id,
            market_platform_id=market_platform_id,
            taker_side=taker_side,
            trader_id=trader_id,
            limit=limit,
            max_rows=max_rows,
        )

    def fills_models(self, **filters: Any) -> Any:
        return self.clickhouse.fills(**filters)

    def orderbook_snapshots(
        self,
        *,
        start_time: datetime | str,
        end_time: datetime | str,
        platform: StringFilter = None,
        market: Market | str | UUID | None = None,
        market_id: IDFilter = None,
        market_platform_id: StringFilter = None,
        state: StringFilter = None,
        continuity: StringFilter = None,
        frame: FrameKind | None = None,
        **filters: Any,
    ) -> Any:
        return self.clickhouse.orderbook_snapshots(
            start_time=start_time,
            end_time=end_time,
            platform=platform,
            market=market,
            market_id=market_id,
            market_platform_id=market_platform_id,
            state=state,
            continuity=continuity,
            frame=validate_frame(frame or self.frame),
            **filters,
        )


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
