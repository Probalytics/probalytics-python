from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, cast

FrameKind = Literal["polars", "pandas"]
VALID_FRAMES = ("polars", "pandas")


def validate_frame(frame: str) -> FrameKind:
    if frame not in VALID_FRAMES:
        raise ValueError("frame must be 'polars' or 'pandas'")
    return cast(FrameKind, frame)


def normalize_time(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        original = value
        value = value.strip()
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"invalid datetime string: {original!r}") from error
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def dataframe_to_frame(df: Any, frame: FrameKind = "polars") -> Any:
    frame = validate_frame(frame)
    if frame == "polars":
        import pandas as pd
        import polars as pl

        if isinstance(df, pl.DataFrame):
            return df
        if isinstance(df, pd.DataFrame):
            return pl.from_pandas(df)
        return pl.DataFrame(df)
    if frame == "pandas":
        import pandas as pd
        import polars as pl

        if isinstance(df, pd.DataFrame):
            return df
        if isinstance(df, pl.DataFrame):
            return df.to_pandas()
        return pd.DataFrame(df)
    raise ValueError("frame must be 'polars' or 'pandas'")
