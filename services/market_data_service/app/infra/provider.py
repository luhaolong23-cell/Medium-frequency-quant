from datetime import date, datetime, time, timedelta, timezone
import importlib
import math
import random
import time as time_module
from statistics import fmean, median, pstdev
from urllib.parse import quote

import httpx

from packages.domain_core.market.entities import Market, MarketFeature, MarketObservation
from packages.shared.settings import DataSourcesConfig


class MockMarketDataProvider:
    source_mode = "mock"

    def fetch_daily(self, markets, trade_date: date) -> list[MarketObservation]:
        return [self._build_observation(market, trade_date) for market in markets]

    @staticmethod
    def _build_observation(market, trade_date: date) -> MarketObservation:
        seed = sum(ord(char) for char in market.market_code) + trade_date.toordinal()
        rng = random.Random(seed)
        close = round(100 + rng.uniform(-15, 25), 4)
        ma_5 = round(close - rng.uniform(-2, 2), 4)
        ma_10 = round(close - rng.uniform(-3, 3), 4)
        ma_20 = round(close - rng.uniform(-4, 4), 4)
        ma_60 = round(close - rng.uniform(-6, 6), 4)
        ma_120 = round(close - rng.uniform(-8, 8), 4)
        ma_200 = round(close - rng.uniform(-10, 10), 4)
        ret_1d = round(rng.uniform(-0.03, 0.05), 4)
        ret_5d = round(rng.uniform(-0.08, 0.12), 4)
        ret_60d = round(rng.uniform(-0.15, 0.25), 4)
        ret_120d = round(rng.uniform(-0.20, 0.35), 4)
        vol_20d = round(rng.uniform(0.08, 0.35), 4)
        drawdown_60d = round(rng.uniform(-0.25, -0.01), 4)
        relative_strength_world = round(rng.uniform(-0.18, 0.18), 4)
        fx_ret_60d = round(rng.uniform(-0.08, 0.08), 4)
        avg_volume_prior = round(rng.uniform(50_000_000, 180_000_000), 2)
        volume_ratio_5d = round(rng.uniform(0.85, 1.8), 4)
        avg_volume_recent = round(avg_volume_prior * volume_ratio_5d, 2)
        turnover_ratio_20d = round(rng.uniform(0.9, 2.2), 4)
        avg_turnover_ratio_3d = round(rng.uniform(0.9, 1.8), 4)
        volume_up_days_2d = rng.randint(0, 2)
        volume_up_days_3d = rng.randint(max(volume_up_days_2d, 0), 3)
        consecutive_up_days = rng.randint(0, 5)
        consecutive_up_weeks = rng.randint(0, 4)
        primary_proxy = sorted(market.proxies, key=lambda item: item.priority)[0]
        return MarketObservation(
            market_code=market.market_code,
            trade_date=trade_date,
            price_proxy=primary_proxy.symbol,
            close=close,
            ma_120=ma_120,
            ma_200=ma_200,
            ret_60d=ret_60d,
            ret_120d=ret_120d,
            vol_20d=vol_20d,
            drawdown_60d=drawdown_60d,
            relative_strength_world=relative_strength_world,
            fx_ret_60d=fx_ret_60d,
            avg_volume_recent=avg_volume_recent,
            avg_volume_prior=avg_volume_prior,
            volume_ratio_5d=volume_ratio_5d,
            consecutive_up_weeks=consecutive_up_weeks,
            ma_5=ma_5,
            ma_10=ma_10,
            ma_20=ma_20,
            ma_60=ma_60,
            ret_1d=ret_1d,
            ret_5d=ret_5d,
            turnover_ratio_20d=turnover_ratio_20d,
            avg_turnover_ratio_3d=avg_turnover_ratio_3d,
            volume_up_days_2d=volume_up_days_2d,
            volume_up_days_3d=volume_up_days_3d,
            consecutive_up_days=consecutive_up_days,
            source="mock",
        )


class YahooFinanceMarketDataProvider:
    source_mode = "yahoo"

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        chart_base_url: str,
        world_benchmark_symbol: str,
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
        self._chart_base_url = chart_base_url.rstrip("/")
        self._world_benchmark_symbol = world_benchmark_symbol
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockMarketDataProvider()
        self._history_cache: dict[tuple[str, date], list[tuple[date, float, float]]] = {}
        self._max_attempts = max(1, data_sources_config.retry.max_attempts)
        self._backoff_seconds = max(0, data_sources_config.retry.backoff_seconds)

    def fetch_daily(self, markets: list[Market], trade_date: date) -> list[MarketObservation]:
        benchmark_history = self._safe_fetch_history(self._world_benchmark_symbol, trade_date)
        return [
            self._build_market_observation(market, trade_date, benchmark_history)
            for market in markets
        ]

    def _build_market_observation(
        self,
        market: Market,
        trade_date: date,
        benchmark_history: list[tuple[date, float, float]] | None,
    ) -> MarketObservation:
        errors: list[str] = []
        for proxy in sorted(market.proxies, key=lambda item: item.priority):
            try:
                history = self._fetch_history(proxy.symbol, trade_date)
                return self._history_to_observation(
                    market=market,
                    trade_date=trade_date,
                    proxy_symbol=proxy.symbol,
                    history=history,
                    benchmark_history=benchmark_history,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{proxy.symbol}: {exc}")
        if self._allow_mock_fallback:
            return self._mock_provider._build_observation(market, trade_date)
        raise RuntimeError(
            f"Unable to fetch market data for {market.market_code}. Attempts: {'; '.join(errors)}"
        )

    def _history_to_observation(
        self,
        *,
        market: Market,
        trade_date: date,
        proxy_symbol: str,
        history: list[tuple[date, float, float]],
        benchmark_history: list[tuple[date, float, float]] | None,
    ) -> MarketObservation:
        filtered = [(trade_day, close, volume) for trade_day, close, volume in history if trade_day <= trade_date]
        closes = [close for _, close, _ in filtered]
        if len(closes) < 201:
            raise RuntimeError(f"Not enough history for {proxy_symbol}: need 201 closes, got {len(closes)}")

        relative_strength_world = 0.0
        if benchmark_history is not None:
            benchmark_closes = [price for trade_day, price, _ in benchmark_history if trade_day <= trade_date]
            if len(benchmark_closes) >= 121:
                relative_strength_world = _period_return(closes, 120) - _period_return(benchmark_closes, 120)

        recent_volume_window = [volume for _, _, volume in filtered[-5:]]
        prior_volume_window = [volume for _, _, volume in filtered[-10:-5]]
        avg_volume_recent = fmean(recent_volume_window) if recent_volume_window else 0.0
        avg_volume_prior = fmean(prior_volume_window) if prior_volume_window else 0.0
        volume_ratio_5d = round(avg_volume_recent / avg_volume_prior, 4) if avg_volume_prior > 0 else 0.0

        turnover_series = [close * volume for _, close, volume in filtered]
        turnover_ratio_20d = round(_turnover_ratio(turnover_series, 1, 20), 4)
        avg_turnover_ratio_3d = round(_average_turnover_ratio(turnover_series, 3, 20), 4)

        return MarketObservation(
            market_code=market.market_code,
            trade_date=trade_date,
            price_proxy=proxy_symbol,
            close=round(closes[-1], 4),
            ma_120=round(fmean(closes[-120:]), 4),
            ma_200=round(fmean(closes[-200:]), 4),
            ret_60d=round(_period_return(closes, 60), 4),
            ret_120d=round(_period_return(closes, 120), 4),
            vol_20d=round(_annualized_volatility(closes, 20), 4),
            drawdown_60d=round(_max_drawdown(closes[-60:]), 4),
            relative_strength_world=round(relative_strength_world, 4),
            fx_ret_60d=0.0,
            avg_volume_recent=round(avg_volume_recent, 2),
            avg_volume_prior=round(avg_volume_prior, 2),
            volume_ratio_5d=volume_ratio_5d,
            consecutive_up_weeks=_consecutive_up_weeks(closes),
            ma_5=round(fmean(closes[-5:]), 4),
            ma_10=round(fmean(closes[-10:]), 4),
            ma_20=round(fmean(closes[-20:]), 4),
            ma_60=round(fmean(closes[-60:]), 4),
            ret_1d=round(_period_return(closes, 1), 4),
            ret_5d=round(_period_return(closes, 5), 4),
            turnover_ratio_20d=turnover_ratio_20d,
            avg_turnover_ratio_3d=avg_turnover_ratio_3d,
            volume_up_days_2d=_volume_up_days(filtered, 2),
            volume_up_days_3d=_volume_up_days(filtered, 3),
            consecutive_up_days=_consecutive_up_days(closes),
            source="yahoo",
        )

    def _safe_fetch_history(self, symbol: str, trade_date: date) -> list[tuple[date, float, float]] | None:
        try:
            return self._fetch_history(symbol, trade_date)
        except Exception:  # noqa: BLE001
            return None

    def _fetch_history(self, symbol: str, trade_date: date) -> list[tuple[date, float, float]]:
        cache_key = (symbol, trade_date)
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]
        start_date = trade_date - timedelta(days=600)
        period1 = int(datetime.combine(start_date, time.min, tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(trade_date + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp())
        url = f"{self._chart_base_url}/v8/finance/chart/{quote(symbol, safe='')}"
        payload = self._request_chart_payload(
            url=url,
            params={
                "interval": "1d",
                "period1": period1,
                "period2": period2,
                "includePrePost": "false",
                "events": "div,splits",
            },
        )
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            error = (payload.get("chart") or {}).get("error") or {}
            raise RuntimeError(error.get("description") or f"No chart result returned for {symbol}")
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote_rows = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote_rows.get("close") or []
        volumes = quote_rows.get("volume") or []
        adjusted = ((chart.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
        history: list[tuple[date, float, float]] = []
        for index, timestamp in enumerate(timestamps):
            raw_close = adjusted[index] if index < len(adjusted) and adjusted[index] is not None else closes[index]
            raw_volume = volumes[index] if index < len(volumes) and volumes[index] is not None else 0
            if raw_close is None:
                continue
            trade_day = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
            history.append((trade_day, float(raw_close), float(raw_volume)))
        if not history:
            raise RuntimeError(f"No daily closes returned for {symbol}")
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


class YFinanceMarketDataProvider:
    source_mode = "yfinance"

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        world_benchmark_symbol: str,
        allow_mock_fallback: bool = False,
        ticker_factory=None,
    ) -> None:
        self._data_sources_config = data_sources_config
        self._world_benchmark_symbol = world_benchmark_symbol
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockMarketDataProvider()
        self._history_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._ticker_factory = ticker_factory or _resolve_yfinance_ticker_factory()

    def fetch_daily(self, markets: list[Market], trade_date: date) -> list[MarketObservation]:
        benchmark_history = self._safe_fetch_history(self._world_benchmark_symbol)
        return [
            self._build_market_observation(market, trade_date, benchmark_history)
            for market in markets
        ]

    def _build_market_observation(
        self,
        market: Market,
        trade_date: date,
        benchmark_history: list[tuple[date, float, float]] | None,
    ) -> MarketObservation:
        errors: list[str] = []
        for proxy in sorted(market.proxies, key=lambda item: item.priority):
            try:
                history = self._fetch_history(proxy.symbol)
                return self._history_to_observation(
                    market=market,
                    trade_date=trade_date,
                    proxy_symbol=proxy.symbol,
                    history=history,
                    benchmark_history=benchmark_history,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{proxy.symbol}: {exc}")
        if self._allow_mock_fallback:
            return self._mock_provider._build_observation(market, trade_date)
        raise RuntimeError(
            f"Unable to fetch market data for {market.market_code}. Attempts: {'; '.join(errors)}"
        )

    def _history_to_observation(
        self,
        *,
        market: Market,
        trade_date: date,
        proxy_symbol: str,
        history: list[tuple[date, float, float]],
        benchmark_history: list[tuple[date, float, float]] | None,
    ) -> MarketObservation:
        filtered = [(trade_day, close, volume) for trade_day, close, volume in history if trade_day <= trade_date]
        closes = [close for _, close, _ in filtered]
        if len(closes) < 201:
            raise RuntimeError(f"Not enough history for {proxy_symbol}: need 201 closes, got {len(closes)}")

        relative_strength_world = 0.0
        if benchmark_history is not None:
            benchmark_closes = [price for trade_day, price, _ in benchmark_history if trade_day <= trade_date]
            if len(benchmark_closes) >= 121:
                relative_strength_world = _period_return(closes, 120) - _period_return(benchmark_closes, 120)

        recent_volume_window = [volume for _, _, volume in filtered[-5:]]
        prior_volume_window = [volume for _, _, volume in filtered[-10:-5]]
        avg_volume_recent = fmean(recent_volume_window) if recent_volume_window else 0.0
        avg_volume_prior = fmean(prior_volume_window) if prior_volume_window else 0.0
        volume_ratio_5d = round(avg_volume_recent / avg_volume_prior, 4) if avg_volume_prior > 0 else 0.0

        turnover_series = [close * volume for _, close, volume in filtered]
        turnover_ratio_20d = round(_turnover_ratio(turnover_series, 1, 20), 4)
        avg_turnover_ratio_3d = round(_average_turnover_ratio(turnover_series, 3, 20), 4)

        return MarketObservation(
            market_code=market.market_code,
            trade_date=trade_date,
            price_proxy=proxy_symbol,
            close=round(closes[-1], 4),
            ma_120=round(fmean(closes[-120:]), 4),
            ma_200=round(fmean(closes[-200:]), 4),
            ret_60d=round(_period_return(closes, 60), 4),
            ret_120d=round(_period_return(closes, 120), 4),
            vol_20d=round(_annualized_volatility(closes, 20), 4),
            drawdown_60d=round(_max_drawdown(closes[-60:]), 4),
            relative_strength_world=round(relative_strength_world, 4),
            fx_ret_60d=0.0,
            avg_volume_recent=round(avg_volume_recent, 2),
            avg_volume_prior=round(avg_volume_prior, 2),
            volume_ratio_5d=volume_ratio_5d,
            consecutive_up_weeks=_consecutive_up_weeks(closes),
            ma_5=round(fmean(closes[-5:]), 4),
            ma_10=round(fmean(closes[-10:]), 4),
            ma_20=round(fmean(closes[-20:]), 4),
            ma_60=round(fmean(closes[-60:]), 4),
            ret_1d=round(_period_return(closes, 1), 4),
            ret_5d=round(_period_return(closes, 5), 4),
            turnover_ratio_20d=turnover_ratio_20d,
            avg_turnover_ratio_3d=avg_turnover_ratio_3d,
            volume_up_days_2d=_volume_up_days(filtered, 2),
            volume_up_days_3d=_volume_up_days(filtered, 3),
            consecutive_up_days=_consecutive_up_days(closes),
            source="yfinance",
        )

    def _safe_fetch_history(self, symbol: str) -> list[tuple[date, float, float]] | None:
        try:
            return self._fetch_history(symbol)
        except Exception:  # noqa: BLE001
            return None

    def _fetch_history(self, symbol: str) -> list[tuple[date, float, float]]:
        if symbol in self._history_cache:
            return self._history_cache[symbol]
        ticker = self._ticker_factory(symbol)
        history = ticker.history(period='30mo', interval='1d', auto_adjust=True)
        if history.empty:
            raise RuntimeError(f"No daily closes returned for {symbol}")
        history = history[['Close', 'Volume']].copy()
        rows: list[tuple[date, float, float]] = []
        for timestamp, row in history.iterrows():
            close = row.get('Close')
            if close is None or math.isnan(float(close)):
                continue
            volume = _coerce_number(row.get('Volume'))
            rows.append((timestamp.to_pydatetime().date(), float(close), volume))
        if not rows:
            raise RuntimeError(f"No daily closes returned for {symbol}")
        self._history_cache[symbol] = rows
        return rows


class CompositeMarketDataProvider:
    def __init__(self, providers: list) -> None:
        self._providers = providers

    @property
    def source_mode(self) -> str:
        names = [provider.source_mode for provider in self._providers]
        return f"composite[{','.join(names)}]"

    def fetch_daily(self, markets: list[Market], trade_date: date) -> list[MarketObservation]:
        candidates_by_market: dict[str, list[MarketObservation]] = {market.market_code: [] for market in markets}
        errors: list[str] = []
        for provider in self._providers:
            try:
                observations = provider.fetch_daily(markets, trade_date)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.source_mode}: {exc}")
                continue
            for observation in observations:
                candidates_by_market.setdefault(observation.market_code, []).append(observation)

        selected: list[MarketObservation] = []
        for market in markets:
            candidates = candidates_by_market.get(market.market_code, [])
            if not candidates:
                error_detail = '; '.join(errors) if errors else 'no provider returned data'
                raise RuntimeError(f"No market data candidates for {market.market_code}: {error_detail}")
            selected.append(_select_best_market_observation(candidates, self._providers))
        return selected


class ObservationFeatureBuilder:
    def build(self, observation: MarketObservation) -> MarketFeature:
        return MarketFeature(
            market_code=observation.market_code,
            trade_date=observation.trade_date,
            price_proxy=observation.price_proxy,
            close=observation.close,
            ma_120=observation.ma_120,
            ma_200=observation.ma_200,
            ret_60d=observation.ret_60d,
            ret_120d=observation.ret_120d,
            vol_20d=observation.vol_20d,
            drawdown_60d=observation.drawdown_60d,
            relative_strength_world=observation.relative_strength_world,
            fx_ret_60d=observation.fx_ret_60d,
            avg_volume_recent=observation.avg_volume_recent,
            avg_volume_prior=observation.avg_volume_prior,
            volume_ratio_5d=observation.volume_ratio_5d,
            consecutive_up_weeks=observation.consecutive_up_weeks,
            ma_5=observation.ma_5,
            ma_10=observation.ma_10,
            ma_20=observation.ma_20,
            ma_60=observation.ma_60,
            ret_1d=observation.ret_1d,
            ret_5d=observation.ret_5d,
            turnover_ratio_20d=observation.turnover_ratio_20d,
            avg_turnover_ratio_3d=observation.avg_turnover_ratio_3d,
            volume_up_days_2d=observation.volume_up_days_2d,
            volume_up_days_3d=observation.volume_up_days_3d,
            consecutive_up_days=observation.consecutive_up_days,
            source=observation.source,
        )



def _select_best_market_observation(
    candidates: list[MarketObservation],
    providers: list,
) -> MarketObservation:
    priority = {provider.source_mode: index for index, provider in enumerate(providers)}
    field_names = [
        'close',
        'ma_120',
        'ma_200',
        'ret_60d',
        'ret_120d',
        'vol_20d',
        'drawdown_60d',
        'relative_strength_world',
        'avg_volume_recent',
        'avg_volume_prior',
        'volume_ratio_5d',
        'consecutive_up_weeks',
        'ma_5',
        'ma_10',
        'ma_20',
        'ma_60',
        'ret_1d',
        'ret_5d',
        'turnover_ratio_20d',
        'avg_turnover_ratio_3d',
        'volume_up_days_2d',
        'volume_up_days_3d',
        'consecutive_up_days',
    ]
    medians = _numeric_medians(candidates, field_names)

    def score(candidate: MarketObservation) -> tuple[float, float, float]:
        completeness = sum(1 for field_name in field_names if _is_valid_number(getattr(candidate, field_name)))
        deviation_penalty = 0.0
        for field_name in field_names:
            value = getattr(candidate, field_name)
            pivot = medians.get(field_name)
            if not _is_valid_number(value) or pivot is None:
                continue
            scale = max(abs(pivot), 1.0)
            deviation_penalty += abs(float(value) - pivot) / scale
        priority_rank = priority.get(candidate.source, len(priority))
        source_bonus = 0.1 if candidate.source != 'mock' else 0.0
        return (completeness + source_bonus, -deviation_penalty, -priority_rank)

    return max(candidates, key=score)


def _numeric_medians(candidates: list[MarketObservation], field_names: list[str]) -> dict[str, float]:
    medians: dict[str, float] = {}
    for field_name in field_names:
        values = [float(getattr(candidate, field_name)) for candidate in candidates if _is_valid_number(getattr(candidate, field_name))]
        if values:
            medians[field_name] = float(median(values))
    return medians


def _period_return(closes: list[float], lookback: int) -> float:
    base_price = closes[-(lookback + 1)]
    return (closes[-1] / base_price) - 1.0


def _annualized_volatility(closes: list[float], lookback: int) -> float:
    window = closes[-(lookback + 1):]
    daily_returns = [(current / previous) - 1.0 for previous, current in zip(window, window[1:])]
    if len(daily_returns) < 2:
        return 0.0
    return pstdev(daily_returns) * math.sqrt(252)


def _max_drawdown(closes: list[float]) -> float:
    peak = closes[0]
    worst_drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        worst_drawdown = min(worst_drawdown, (close / peak) - 1.0)
    return worst_drawdown


def _consecutive_up_weeks(closes: list[float], weekly_step: int = 5) -> int:
    if len(closes) < weekly_step + 1:
        return 0
    count = 0
    current_index = len(closes) - 1
    while current_index - weekly_step >= 0:
        if closes[current_index] > closes[current_index - weekly_step]:
            count += 1
            current_index -= weekly_step
            continue
        break
    return count


def _consecutive_up_days(closes: list[float]) -> int:
    if len(closes) < 2:
        return 0
    count = 0
    for previous, current in zip(reversed(closes[:-1]), reversed(closes[1:])):
        if current > previous:
            count += 1
            continue
        break
    return count


def _volume_up_days(history: list[tuple[date, float, float]], comparisons: int) -> int:
    volumes = [volume for _, _, volume in history]
    if len(volumes) < comparisons + 1:
        return 0
    window = volumes[-(comparisons + 1):]
    return sum(1 for previous, current in zip(window[:-1], window[1:]) if current > previous)


def _turnover_ratio(turnover_series: list[float], current_window: int, baseline_window: int) -> float:
    if len(turnover_series) < current_window + baseline_window:
        return 0.0
    current_avg = fmean(turnover_series[-current_window:])
    baseline_avg = fmean(turnover_series[-(current_window + baseline_window):-current_window])
    if baseline_avg <= 0:
        return 0.0
    return current_avg / baseline_avg


def _average_turnover_ratio(turnover_series: list[float], current_window: int, baseline_window: int) -> float:
    return _turnover_ratio(turnover_series, current_window, baseline_window)


def _resolve_yfinance_ticker_factory():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:  # noqa: PERF203
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.Ticker


def _coerce_number(value) -> float:
    if value is None:
        return 0.0
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return number


def _is_valid_number(value) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(value) and not math.isinf(value)
