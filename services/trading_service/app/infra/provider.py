from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import importlib
import math
import random
import time as time_module
from urllib.parse import quote

import httpx

from packages.shared.settings import DataSourcesConfig


class MockPositionDataProvider:
    source_mode = 'mock'

    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        seed = sum(ord(char) for char in ticker) + trade_date.toordinal()
        rng = random.Random(seed)
        rows: list[tuple[date, float, float]] = []
        base_price = 40 + rng.uniform(0, 80)
        base_volume = 5_000_000 + rng.uniform(0, 25_000_000)
        current_price = base_price
        current_volume = base_volume
        start_day = trade_date - timedelta(days=259)
        for offset in range(260):
            current_day = start_day + timedelta(days=offset)
            current_price = max(5.0, current_price * (1 + rng.uniform(-0.025, 0.03)))
            current_volume = max(100_000.0, current_volume * (1 + rng.uniform(-0.12, 0.12)))
            rows.append((current_day, round(current_price, 4), round(current_volume, 2)))
        return rows


class YahooPositionDataProvider:
    source_mode = 'yahoo'

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        chart_base_url: str,
        allow_mock_fallback: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        timeout = httpx.Timeout(
            connect=data_sources_config.timeouts.connect_seconds,
            read=data_sources_config.timeouts.read_seconds,
            write=data_sources_config.timeouts.read_seconds,
            pool=data_sources_config.timeouts.connect_seconds,
        )
        self._client = client or httpx.Client(timeout=timeout)
        self._chart_base_url = chart_base_url.rstrip('/')
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockPositionDataProvider()
        self._history_cache: dict[tuple[str, date], list[tuple[date, float, float]]] = {}
        self._max_attempts = max(1, data_sources_config.retry.max_attempts)
        self._backoff_seconds = max(0, data_sources_config.retry.backoff_seconds)

    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        try:
            return self._fetch_history(ticker, trade_date)
        except Exception:
            if self._allow_mock_fallback:
                return self._mock_provider.fetch_history(ticker, trade_date)
            raise

    def _fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        cache_key = (ticker, trade_date)
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]
        start_date = trade_date - timedelta(days=600)
        period1 = int(datetime.combine(start_date, time.min, tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(trade_date + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp())
        payload = self._request_chart_payload(
            url=f"{self._chart_base_url}/v8/finance/chart/{quote(ticker, safe='')}",
            params={
                'interval': '1d',
                'period1': period1,
                'period2': period2,
                'includePrePost': 'false',
                'events': 'div,splits',
            },
        )
        result = (payload.get('chart') or {}).get('result') or []
        if not result:
            error = (payload.get('chart') or {}).get('error') or {}
            raise RuntimeError(error.get('description') or f'No chart result returned for {ticker}')
        chart = result[0]
        timestamps = chart.get('timestamp') or []
        quote_rows = ((chart.get('indicators') or {}).get('quote') or [{}])[0]
        closes = quote_rows.get('close') or []
        adjusted = ((chart.get('indicators') or {}).get('adjclose') or [{}])[0].get('adjclose') or []
        volumes = quote_rows.get('volume') or []
        history: list[tuple[date, float, float]] = []
        for index, timestamp in enumerate(timestamps):
            raw_close = adjusted[index] if index < len(adjusted) and adjusted[index] is not None else closes[index]
            raw_volume = volumes[index] if index < len(volumes) and volumes[index] is not None else 0
            if raw_close is None:
                continue
            history.append((datetime.fromtimestamp(timestamp, tz=timezone.utc).date(), float(raw_close), float(raw_volume)))
        if not history:
            raise RuntimeError(f'No daily data returned for {ticker}')
        self._history_cache[cache_key] = history
        return history

    def _request_chart_payload(self, *, url: str, params: dict[str, str | int]) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self._max_attempts:
                    break
                if self._backoff_seconds > 0:
                    time_module.sleep(self._backoff_seconds * attempt)
        assert last_error is not None
        raise last_error


class YFinancePositionDataProvider:
    source_mode = 'yfinance'

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        allow_mock_fallback: bool = False,
        ticker_factory=None,
    ) -> None:
        self._data_sources_config = data_sources_config
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockPositionDataProvider()
        self._history_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._ticker_factory = ticker_factory or _resolve_yfinance_ticker_factory()

    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        try:
            history = self._fetch_history(ticker)
            filtered = [row for row in history if row[0] <= trade_date]
            if not filtered:
                raise RuntimeError(f'No history up to {trade_date.isoformat()} for {ticker}')
            return filtered
        except Exception:
            if self._allow_mock_fallback:
                return self._mock_provider.fetch_history(ticker, trade_date)
            raise

    def _fetch_history(self, ticker: str) -> list[tuple[date, float, float]]:
        if ticker in self._history_cache:
            return self._history_cache[ticker]
        history = self._ticker_factory(ticker).history(period='30mo', interval='1d', auto_adjust=True)
        if history.empty:
            raise RuntimeError(f'No daily data returned for {ticker}')
        history = history[['Close', 'Volume']].copy()
        rows: list[tuple[date, float, float]] = []
        for timestamp, row in history.iterrows():
            close = row.get('Close')
            if close is None or math.isnan(float(close)):
                continue
            volume = row.get('Volume')
            if volume is None or math.isnan(float(volume)):
                volume = 0.0
            rows.append((timestamp.to_pydatetime().date(), float(close), float(volume)))
        if not rows:
            raise RuntimeError(f'No daily data returned for {ticker}')
        self._history_cache[ticker] = rows
        return rows


class CompositePositionDataProvider:
    def __init__(self, providers: list) -> None:
        self._providers = providers

    @property
    def source_mode(self) -> str:
        names = [provider.source_mode for provider in self._providers]
        return f"composite[{','.join(names)}]"

    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        errors: list[str] = []
        for provider in self._providers:
            try:
                history = provider.fetch_history(ticker, trade_date)
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{provider.source_mode}: {exc}')
                continue
            if history:
                return history
        error_text = '; '.join(errors) if errors else 'no provider returned data'
        raise RuntimeError(f'No position history for {ticker}: {error_text}')


def _resolve_yfinance_ticker_factory():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.Ticker
