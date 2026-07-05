from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from probalytics.models import Market

StringFilter = str | Sequence[str] | None
IDFilter = str | UUID | Sequence[str | UUID] | None


def market_filter(
    market: Market | str | UUID | None,
    market_id: IDFilter,
    market_platform_id: StringFilter,
    platform: StringFilter,
) -> tuple[IDFilter, StringFilter, StringFilter]:
    if isinstance(market, Market):
        return market.id, market.platform_id, market.platform
    if isinstance(market, UUID):
        return market, market_platform_id, platform
    if isinstance(market, str):
        try:
            return UUID(market), market_platform_id, platform
        except ValueError:
            return market_id, market, platform
    return market_id, market_platform_id, platform
