from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from probalytics._frames import FrameKind


class Platform(StrEnum):
    POLYMARKET = "POLYMARKET"
    KALSHI = "KALSHI"
    PREDICTIT = "PREDICTIT"
    UNKNOWN = "UNKNOWN"


class MarketStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"


class MarketType(StrEnum):
    BINARY = "BINARY"
    MULTIPLE = "MULTIPLE"
    SCALAR = "SCALAR"
    PARLAY = "PARLAY"
    PERPETUAL = "PERPETUAL"
    UNKNOWN = "UNKNOWN"


class ResolutionType(StrEnum):
    STANDARD = "STANDARD"
    SPLIT = "SPLIT"
    VOID = "VOID"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class ProbalyticsModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class Outcome(ProbalyticsModel):
    id: UUID
    platform_id: str
    name: str
    index: int


class OutcomePayout(ProbalyticsModel):
    outcome_id: UUID
    payout: Decimal


class Resolution(ProbalyticsModel):
    type: ResolutionType
    winning_outcome_id: UUID | None = None
    outcome_payouts: list[OutcomePayout] = Field(default_factory=list)
    resolved_by: str = ""
    resolved_at: datetime | None = None


class Market(ProbalyticsModel):
    _client: Any = PrivateAttr(default=None)

    id: UUID
    platform: Platform
    platform_id: str
    slug: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    market_type: MarketType = MarketType.UNKNOWN
    outcomes: list[Outcome] = Field(default_factory=list)
    status: MarketStatus
    created_at: datetime
    opened_at: datetime | None = None
    closes_at: datetime | None = None
    resolves_at: datetime | None = None
    end_date: datetime | None = None
    reset_at: datetime | None = None
    resolution: Resolution | None = None

    def fills(
        self,
        *,
        client: Any | None = None,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        taker_side: str | list[str] | None = None,
        trader_id: str | list[str] | None = None,
        limit: int = 1000,
        max_rows: int | None = None,
        frame: FrameKind | None = None,
    ) -> Any:
        return self._require_client(client).fills(
            market=self,
            start_time=start_time,
            end_time=end_time,
            taker_side=taker_side,
            trader_id=trader_id,
            limit=limit,
            max_rows=max_rows,
            frame=frame,
        )

    def fills_models(
        self,
        *,
        client: Any | None = None,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        taker_side: str | list[str] | None = None,
        trader_id: str | list[str] | None = None,
        limit: int = 1000,
        max_rows: int | None = None,
    ) -> list[Any]:
        return self._require_client(client).fills_models(
            market=self,
            start_time=start_time,
            end_time=end_time,
            taker_side=taker_side,
            trader_id=trader_id,
            limit=limit,
            max_rows=max_rows,
        )

    def orderbook_snapshots(
        self,
        *,
        start_time: datetime | str,
        end_time: datetime | str,
        client: Any | None = None,
        limit: int = 1000,
        frame: FrameKind | None = None,
    ) -> Any:
        return self._require_client(client).orderbook_snapshots(
            market=self,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            frame=frame,
        )

    def _bind_client(self, client: Any) -> "Market":
        self._client = client
        return self

    def _require_client(self, client: Any | None) -> Any:
        resolved = client or self._client
        if resolved is None:
            raise ValueError(
                "market is not bound to a client; pass client=... or load it with client.markets()"
            )
        return resolved


class Fill(ProbalyticsModel):
    id: UUID
    market_id: UUID
    market_platform_id: str
    platform: Platform
    platform_id: str
    outcome: Outcome
    size: Decimal
    price: Decimal
    normalized_price: Decimal
    taker_side: OrderSide
    taker_cash_flow: Decimal
    maker_cash_flow: Decimal
    taker_id: str | None = None
    maker_id: str | None = None
    fee: Decimal
    timestamp: datetime


class BookLevel(ProbalyticsModel):
    price: Decimal
    size: Decimal


class OrderbookSnapshot(ProbalyticsModel):
    market_id: UUID
    market_platform_id: str
    platform: Platform
    outcome: Outcome
    bids: list[BookLevel] = Field(default_factory=list)
    asks: list[BookLevel] = Field(default_factory=list)
    timestamp: datetime


def model_records(models: list[ProbalyticsModel]) -> list[dict[str, Any]]:
    return [m.model_dump(mode="python") for m in models]
