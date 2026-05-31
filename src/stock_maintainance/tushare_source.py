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
