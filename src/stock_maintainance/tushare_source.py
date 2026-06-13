from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import load_sources
from .env import get_tushare_token


@dataclass(frozen=True)
class RateLimitPolicy:
    default_sleep_seconds: float
    financial_sleep_seconds: float
    max_retries: int


class TushareClient:
    def __init__(self) -> None:
        import tushare as ts

        self._ts = ts
        self._pro = ts.pro_api(get_tushare_token())
        policy = load_sources()["tushare"]["rate_limit_policy"]
        self._rate_limit = RateLimitPolicy(
            default_sleep_seconds=float(policy.get("default_sleep_seconds", 0.35)),
            financial_sleep_seconds=float(policy.get("financial_sleep_seconds", 0.4)),
            max_retries=int(policy.get("max_retries", 3)),
        )

    def call(self, api_name: str, **params: Any) -> pd.DataFrame:
        return self._call_once(api_name, **params)

    def call_paged(
        self,
        api_name: str,
        *,
        page_size: int = 5000,
        max_pages: int | None = None,
        **params: Any,
    ) -> pd.DataFrame:
        """Fetch APIs that may be truncated by Tushare limit/offset paging."""
        frames: list[pd.DataFrame] = []
        offset = int(params.pop("offset", 0) or 0)
        page = 0
        while True:
            df = self._call_once(api_name, **params, limit=page_size, offset=offset)
            page += 1
            if df.empty:
                break
            frames.append(df)
            if len(df) < page_size:
                break
            if max_pages is not None and page >= max_pages:
                break
            offset += page_size
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _call_once(self, api_name: str, **params: Any) -> pd.DataFrame:
        sleep_seconds = self._sleep_seconds(api_name)
        last_error: Exception | None = None
        for attempt in range(1, self._rate_limit.max_retries + 1):
            try:
                func = getattr(self._pro, api_name)
                df = func(**params)
                time.sleep(sleep_seconds)
                if df is None:
                    return pd.DataFrame()
                return df
            except Exception as exc:  # noqa: BLE001 - API wrappers raise broad exceptions.
                last_error = exc
                time.sleep(sleep_seconds * attempt * 2)
        assert last_error is not None
        raise last_error

    def _sleep_seconds(self, api_name: str) -> float:
        financial_apis = {"income", "balancesheet", "cashflow", "fina_indicator"}
        if api_name in financial_apis:
            return self._rate_limit.financial_sleep_seconds
        return self._rate_limit.default_sleep_seconds
