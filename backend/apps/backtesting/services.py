from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import sqrt
from statistics import pstdev
from typing import Any

from django.db import transaction
from django.utils import timezone as django_timezone

from apps.backtesting.models import BacktestPriceBar, BacktestResult, BacktestRun, StrategyConfig
from apps.market_data.clients.finnhub import FinnhubClient
from apps.market_data.models import Company


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _rolling_min(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            out.append(None)
        else:
            out.append(min(values[idx - window + 1 : idx + 1]))
    return out


def _rolling_max(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            out.append(None)
        else:
            out.append(max(values[idx - window + 1 : idx + 1]))
    return out


def _rolling_mean(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            out.append(None)
        else:
            sample = values[idx - window + 1 : idx + 1]
            out.append(sum(sample) / len(sample))
    return out


def _compute_rsi(closes: list[float], window: int = 14) -> list[float | None]:
    if not closes:
        return []

    deltas = [0.0]
    for idx in range(1, len(closes)):
        deltas.append(closes[idx] - closes[idx - 1])

    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]

    avg_gain = _rolling_mean(gains, window)
    avg_loss = _rolling_mean(losses, window)

    out: list[float | None] = []
    for gain, loss in zip(avg_gain, avg_loss):
        if gain is None or loss is None:
            out.append(None)
            continue
        if loss == 0:
            out.append(100.0)
            continue
        rs = gain / loss
        out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


@dataclass(slots=True)
class BacktestExecutionResult:
    backtest_run_id: str
    ticker: str
    metrics: dict[str, Any]
    summary: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    drawdown_curve: list[dict[str, Any]]
    signal_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    monthly_return_table: list[dict[str, Any]]


class HistoricalPriceIngestionService:
    def __init__(self, client: FinnhubClient | None = None) -> None:
        self.client = client or FinnhubClient()

    def ensure_daily_bars(
        self,
        *,
        company: Company,
        start_date: date,
        end_date: date,
        use_stored_data: bool = True,
    ) -> list[BacktestPriceBar]:
        if use_stored_data:
            existing = list(
                BacktestPriceBar.objects.filter(
                    company=company,
                    resolution=BacktestPriceBar.RESOLUTION_DAY,
                    start_at__date__gte=start_date,
                    start_at__date__lte=end_date,
                ).order_by("start_at")
            )
            total_days = (end_date - start_date).days + 1
            if len(existing) >= max(total_days // 3, 30):
                return existing

        response = self.client.get_stock_candles(
            symbol=company.finnhub_symbol or company.ticker,
            resolution="D",
            from_timestamp=int(datetime.combine(start_date, time.min, tzinfo=timezone.utc).timestamp()),
            to_timestamp=int(datetime.combine(end_date, time.max, tzinfo=timezone.utc).timestamp()),
        )
        payload = response.payload or {}
        if not isinstance(payload, dict) or payload.get("s") != "ok":
            raise ValueError(f"No historical candle data returned for {company.ticker}.")

        times = payload.get("t") or []
        opens = payload.get("o") or []
        highs = payload.get("h") or []
        lows = payload.get("l") or []
        closes = payload.get("c") or []
        volumes = payload.get("v") or []

        with transaction.atomic():
            for idx, ts in enumerate(times):
                start_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                end_at = start_at + timedelta(days=1)
                BacktestPriceBar.objects.update_or_create(
                    company=company,
                    resolution=BacktestPriceBar.RESOLUTION_DAY,
                    start_at=start_at,
                    defaults={
                        "source_name": "finnhub",
                        "symbol": company.finnhub_symbol or company.ticker,
                        "end_at": end_at,
                        "open_price": _to_decimal(opens[idx]),
                        "high_price": _to_decimal(highs[idx]),
                        "low_price": _to_decimal(lows[idx]),
                        "close_price": _to_decimal(closes[idx]),
                        "volume": _to_decimal(volumes[idx]),
                        "payload_json": {
                            "o": opens[idx],
                            "h": highs[idx],
                            "l": lows[idx],
                            "c": closes[idx],
                            "v": volumes[idx],
                            "t": ts,
                        },
                        "fetched_at": django_timezone.now(),
                    },
                )

        return list(
            BacktestPriceBar.objects.filter(
                company=company,
                resolution=BacktestPriceBar.RESOLUTION_DAY,
                start_at__date__gte=start_date,
                start_at__date__lte=end_date,
            ).order_by("start_at")
        )


class StrategyLibrary:
    @staticmethod
    def momentum_details(
        *,
        rows: list[dict[str, Any]],
        lookback_window: int,
        breakout_threshold_pct: float = 0.0,
        exit_lookback_window: int | None = None,
    ) -> list[dict[str, Any]]:
        if lookback_window <= 1:
            raise ValueError("lookback_window must be greater than 1.")

        if exit_lookback_window is None:
            exit_lookback_window = max(5, lookback_window // 2)

        closes = [float(row["close"]) for row in rows]
        highs = [float(row["high"]) for row in rows]
        breakout_levels = _rolling_max(highs, lookback_window)
        exit_levels = _rolling_mean(closes, exit_lookback_window)

        details: list[dict[str, Any]] = []
        current_position = 0

        for idx, row in enumerate(rows):
            close = float(row["close"])
            breakout = breakout_levels[idx]
            exit_level = exit_levels[idx]

            next_position = current_position
            event = "HOLD"
            reason = ""

            if breakout is not None and current_position == 0:
                trigger = breakout * (1.0 + breakout_threshold_pct / 100.0)
                if close >= trigger:
                    next_position = 1
                    event = "BUY"
                    reason = "Momentum breakout confirmed."

            elif current_position == 1 and exit_level is not None:
                if close < exit_level:
                    next_position = 0
                    event = "SELL"
                    reason = "Price fell below exit moving average."

            details.append(
                {
                    "date": row["date"],
                    "target_position": next_position,
                    "event": event,
                    "reason": reason,
                    "short_ma": round(exit_level, 6) if exit_level is not None else None,
                    "long_ma": round(breakout, 6) if breakout is not None else None,
                    "rsi": None,
                    "support": None,
                    "resistance": None,
                    "avg_volume": None,
                    "volume_spike": None,
                }
            )
            current_position = next_position

        return details

    @staticmethod
    def mean_reversion_details(
        *,
        rows: list[dict[str, Any]],
        mean_window: int | None = None,
        std_window: int | None = None,
        lookback_window: int | None = None,
        z_entry: float,
        z_exit: float,
    ) -> list[dict[str, Any]]:
        fallback_window = int(lookback_window or 20)
        mean_window = int(mean_window or fallback_window)
        std_window = int(std_window or fallback_window)

        if mean_window <= 1 or std_window <= 1:
            raise ValueError("mean_window and std_window must be greater than 1.")

        closes = [float(row["close"]) for row in rows]
        mean_values = _rolling_mean(closes, mean_window)

        details: list[dict[str, Any]] = []
        current_position = 0

        for idx, row in enumerate(rows):
            close = float(row["close"])
            mean_value = mean_values[idx]

            z_score = None
            if idx + 1 >= std_window:
                sample = closes[idx - std_window + 1 : idx + 1]
                std = pstdev(sample) if len(sample) > 1 else 0.0
                if std > 0 and mean_value is not None:
                    z_score = (close - mean_value) / std

            next_position = current_position
            event = "HOLD"
            reason = ""

            if z_score is not None:
                if current_position == 0 and z_score <= -z_entry:
                    next_position = 1
                    event = "BUY"
                    reason = "Price deviated below rolling mean."
                elif current_position == 1 and z_score >= -z_exit:
                    next_position = 0
                    event = "SELL"
                    reason = "Price reverted toward rolling mean."

            details.append(
                {
                    "date": row["date"],
                    "target_position": next_position,
                    "event": event,
                    "reason": reason,
                    "short_ma": round(mean_value, 6) if mean_value is not None else None,
                    "long_ma": None,
                    "rsi": round(z_score, 6) if z_score is not None else None,
                    "support": None,
                    "resistance": None,
                    "avg_volume": None,
                    "volume_spike": None,
                }
            )
            current_position = next_position

        return details
    @staticmethod
    def sma_crossover_details(*, rows: list[dict[str, Any]], short_window: int, long_window: int) -> list[dict[str, Any]]:
        if short_window <= 0 or long_window <= 0:
            raise ValueError("short_window and long_window must be positive.")
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window.")

        closes = [float(row["close"]) for row in rows]
        short_ma = _rolling_mean(closes, short_window)
        long_ma = _rolling_mean(closes, long_window)

        details: list[dict[str, Any]] = []
        current_position = 0

        for idx, row in enumerate(rows):
            next_position = current_position
            event = "HOLD"
            reason = ""

            if short_ma[idx] is not None and long_ma[idx] is not None:
                if current_position == 0 and short_ma[idx] > long_ma[idx]:
                    next_position = 1
                    event = "BUY"
                    reason = "Short moving average crossed above long moving average."
                elif current_position == 1 and short_ma[idx] <= long_ma[idx]:
                    next_position = 0
                    event = "SELL"
                    reason = "Short moving average fell back below long moving average."

            details.append(
                {
                    "date": row["date"],
                    "target_position": next_position,
                    "event": event,
                    "reason": reason,
                    "short_ma": round(short_ma[idx], 6) if short_ma[idx] is not None else None,
                    "long_ma": round(long_ma[idx], 6) if long_ma[idx] is not None else None,
                    "rsi": None,
                    "support": None,
                    "resistance": None,
                    "volume_spike": None,
                }
            )
            current_position = next_position

        return details

    @staticmethod
    def support_resistance_rsi_volume_details(
        *,
        rows: list[dict[str, Any]],
        support_window: int,
        resistance_window: int,
        rsi_window: int,
        rsi_buy: float,
        rsi_sell: float,
        volume_window: int,
        volume_multiplier: float,
        buy_tolerance_pct: float,
        sell_tolerance_pct: float,
    ) -> list[dict[str, Any]]:
        closes = [float(row["close"]) for row in rows]
        highs = [float(row["high"]) for row in rows]
        lows = [float(row["low"]) for row in rows]
        volumes = [float(row["volume"]) for row in rows]

        support_levels = _rolling_min(lows, support_window)
        resistance_levels = _rolling_max(highs, resistance_window)
        rsi_values = _compute_rsi(closes, rsi_window)
        avg_volumes = _rolling_mean(volumes, volume_window)

        details: list[dict[str, Any]] = []
        current_position = 0

        for idx, row in enumerate(rows):
            close = float(row["close"])
            support = support_levels[idx]
            resistance = resistance_levels[idx]
            rsi = rsi_values[idx]
            avg_volume = avg_volumes[idx]
            volume = volumes[idx]

            near_support = False
            near_resistance = False
            volume_spike = False

            if support is not None:
                near_support = close <= support * (1.0 + buy_tolerance_pct / 100.0)
            if resistance is not None:
                near_resistance = close >= resistance * (1.0 - sell_tolerance_pct / 100.0)
            if avg_volume is not None and avg_volume > 0:
                volume_spike = volume >= avg_volume * volume_multiplier

            next_position = current_position
            event = "HOLD"
            reason = ""

            if current_position == 0:
                if near_support and rsi is not None and rsi <= rsi_buy and volume_spike:
                    next_position = 1
                    event = "BUY"
                    reason = "Price near support, RSI oversold, and volume spike confirmed entry."
            else:
                if (near_resistance and volume_spike) or (rsi is not None and rsi >= rsi_sell):
                    next_position = 0
                    event = "SELL"
                    reason = "Price near resistance or RSI overbought signaled exit."

            details.append(
                {
                    "date": row["date"],
                    "target_position": next_position,
                    "event": event,
                    "reason": reason,
                    "short_ma": None,
                    "long_ma": None,
                    "rsi": round(rsi, 6) if rsi is not None else None,
                    "support": round(support, 6) if support is not None else None,
                    "resistance": round(resistance, 6) if resistance is not None else None,
                    "avg_volume": round(avg_volume, 6) if avg_volume is not None else None,
                    "volume_spike": volume_spike,
                }
            )
            current_position = next_position

        return details


class BacktestExecutionService:
    def build_strategy_config(
        self,
        *,
        strategy_type: str,
        config_json: dict[str, Any],
    ) -> StrategyConfig:
        config_parts = [f"{k}={config_json[k]}" for k in sorted(config_json.keys())]
        name = f"{strategy_type}:{'|'.join(config_parts)}"
        strategy_config, _created = StrategyConfig.objects.get_or_create(
            name=name,
            strategy_type=strategy_type,
            defaults={
                "description": "Auto-generated strategy configuration.",
                "config_json": config_json,
                "is_active": True,
            },
        )
        if strategy_config.config_json != config_json:
            strategy_config.config_json = config_json
            strategy_config.save(update_fields=["config_json", "updated_at"])
        return strategy_config

    @transaction.atomic
    def create_run(
        self,
        *,
        company: Company,
        strategy_type: str,
        strategy_config: StrategyConfig,
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        position_size: Decimal,
        commission_bps: Decimal,
        resolution: str = "D",
        benchmark_symbol: str = "",
        request_payload_json: dict[str, Any] | None = None,
        job_run=None,
    ) -> BacktestRun:
        return BacktestRun.objects.create(
            company=company,
            strategy_config=strategy_config,
            job_run=job_run,
            name=f"{company.ticker} {strategy_type} {start_date} to {end_date}",
            strategy_type=strategy_type,
            resolution=resolution,
            benchmark_symbol=benchmark_symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            position_size=position_size,
            commission_bps=commission_bps,
            status=BacktestRun.STATUS_PENDING,
            request_payload_json=request_payload_json or {},
        )

    def _build_rows_from_bars(self, bars: list[BacktestPriceBar]) -> list[dict[str, Any]]:
        return [
            {
                "date": bar.start_at.date().isoformat(),
                "open": float(bar.open_price),
                "high": float(bar.high_price),
                "low": float(bar.low_price),
                "close": float(bar.close_price),
                "volume": float(bar.volume),
            }
            for bar in bars
        ]

    def _build_strategy_details(
        self,
        *,
        strategy_type: str,
        rows: list[dict[str, Any]],
        config_json: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if strategy_type == "sma_crossover":
            return StrategyLibrary.sma_crossover_details(
                rows=rows,
                short_window=int(config_json["short_window"]),
                long_window=int(config_json["long_window"]),
            )

        if strategy_type == "support_resistance_rsi_volume":
            return StrategyLibrary.support_resistance_rsi_volume_details(
                rows=rows,
                support_window=int(config_json["support_window"]),
                resistance_window=int(config_json["resistance_window"]),
                rsi_window=int(config_json["rsi_window"]),
                rsi_buy=float(config_json["rsi_buy"]),
                rsi_sell=float(config_json["rsi_sell"]),
                volume_window=int(config_json["volume_window"]),
                volume_multiplier=float(config_json["volume_multiplier"]),
                buy_tolerance_pct=float(config_json["buy_tolerance_pct"]),
                sell_tolerance_pct=float(config_json["sell_tolerance_pct"]),
            )

        if strategy_type == "momentum":
            return StrategyLibrary.momentum_details(
                rows=rows,
                lookback_window=int(config_json.get("lookback_window", 90)),
                breakout_threshold_pct=float(config_json.get("breakout_threshold_pct", 0.0)),
                exit_lookback_window=int(
                    config_json.get(
                        "exit_lookback_window",
                        max(5, int(config_json.get("lookback_window", 90)) // 2),
                    )
                ),
            )

        if strategy_type == "mean_reversion":
            return StrategyLibrary.mean_reversion_details(
                rows=rows,
                mean_window=int(config_json.get("mean_window", config_json.get("lookback_window", 20))),
                std_window=int(config_json.get("std_window", config_json.get("lookback_window", 20))),
                lookback_window=int(config_json.get("lookback_window", 20)),
                z_entry=float(config_json.get("z_entry", 1.5)),
                z_exit=float(config_json.get("z_exit", 0.25)),
            )

        raise ValueError(f"Unsupported strategy_type '{strategy_type}'.")

    def run_backtest(
        self,
        *,
        backtest_run: BacktestRun,
        config_json: dict[str, Any],
        use_stored_data: bool = True,
    ) -> BacktestExecutionResult:
        backtest_run.status = BacktestRun.STATUS_RUNNING
        backtest_run.started_at = django_timezone.now()
        backtest_run.error_payload_json = {}
        backtest_run.save(update_fields=["status", "started_at", "error_payload_json", "updated_at"])

        bars = HistoricalPriceIngestionService().ensure_daily_bars(
            company=backtest_run.company,
            start_date=backtest_run.start_date,
            end_date=backtest_run.end_date,
            use_stored_data=use_stored_data,
        )
        rows = self._build_rows_from_bars(bars)
        if len(rows) < 30:
            raise ValueError("Not enough historical bars to run the strategy.")

        details = self._build_strategy_details(
            strategy_type=backtest_run.strategy_type,
            rows=rows,
            config_json=config_json,
        )

        initial_capital = float(backtest_run.initial_capital)
        position_size = float(backtest_run.position_size)
        commission_rate = float(backtest_run.commission_bps) / 10000.0

        equity = initial_capital
        peak_equity = initial_capital
        equity_curve: list[dict[str, Any]] = []
        drawdown_curve: list[dict[str, Any]] = []
        signal_curve: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        daily_returns: list[float] = []

        previous_position = 0
        previous_close = float(rows[0]["close"])
        entry_equity = None
        entry_price = None
        entry_date = None

        for idx, row in enumerate(rows):
            detail = details[idx]
            target_position = int(detail["target_position"])
            current_close = float(row["close"])
            date_value = row["date"]

            if idx > 0:
                asset_return = (current_close / previous_close) - 1.0
                applied_position = previous_position * position_size
                strategy_return = asset_return * applied_position

                trade_cost = 0.0
                if target_position != previous_position:
                    trade_cost = commission_rate * abs(target_position - previous_position) * position_size

                    trade_record = {
                        "date": date_value,
                        "action": detail["event"],
                        "price": round(current_close, 6),
                        "position_after": target_position,
                        "estimated_cost_pct": round(trade_cost * 100.0, 6),
                        "reason": detail.get("reason", ""),
                    }

                    if target_position == 1 and previous_position == 0:
                        entry_price = current_close
                        entry_equity = equity
                        entry_date = date_value

                    if target_position == 0 and previous_position == 1 and entry_price is not None:
                        trade_return_pct = ((current_close / entry_price) - 1.0) * 100.0
                        trade_record["entry_date"] = entry_date
                        trade_record["trade_return_pct"] = round(trade_return_pct, 6)
                        entry_price = None
                        entry_equity = None
                        entry_date = None

                    trades.append(trade_record)

                strategy_return_after_cost = strategy_return - trade_cost
                equity *= 1.0 + strategy_return_after_cost
                daily_returns.append(strategy_return_after_cost)

            peak_equity = max(peak_equity, equity)
            drawdown = 0.0 if peak_equity == 0 else (equity / peak_equity) - 1.0

            equity_curve.append(
                {
                    "date": date_value,
                    "equity": round(equity, 6),
                    "close": round(current_close, 6),
                    "position": previous_position,
                }
            )
            drawdown_curve.append(
                {
                    "date": date_value,
                    "drawdown_pct": round(drawdown * 100.0, 6),
                }
            )
            signal_curve.append(
                {
                    "date": date_value,
                    "open": round(float(row["open"]), 6),
                    "high": round(float(row["high"]), 6),
                    "low": round(float(row["low"]), 6),
                    "close": round(float(current_close), 6),
                    "position": target_position,
                    "event": detail["event"],
                    "reason": detail.get("reason", ""),
                    "short_ma": detail.get("short_ma"),
                    "long_ma": detail.get("long_ma"),
                    "rsi": detail.get("rsi"),
                    "support": detail.get("support"),
                    "resistance": detail.get("resistance"),
                    "avg_volume": detail.get("avg_volume"),
                    "volume": round(float(row["volume"]), 6),
                    "volume_spike": detail.get("volume_spike"),
                }
            )

            previous_position = target_position
            previous_close = current_close

        total_return = (equity / initial_capital) - 1.0
        bars_used = max(len(rows), 1)
        annualized_return = ((1.0 + total_return) ** (252.0 / max(len(daily_returns), 1))) - 1.0 if daily_returns else 0.0
        volatility = pstdev(daily_returns) * sqrt(252.0) if len(daily_returns) > 1 else 0.0
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0.0
        max_drawdown = min((row["drawdown_pct"] for row in drawdown_curve), default=0.0)
        exposure_days = sum(1 for row in signal_curve if int(row.get("position", 0)) > 0)

        buy_hold_return = (float(rows[-1]["close"]) / float(rows[0]["close"])) - 1.0
        alpha_vs_buy_hold = total_return - buy_hold_return

        closed_trade_returns = [
            float(trade["trade_return_pct"])
            for trade in trades
            if trade.get("trade_return_pct") is not None
        ]
        trade_wins = sum(1 for value in closed_trade_returns if value > 0)
        trade_win_rate = (trade_wins / len(closed_trade_returns) * 100.0) if closed_trade_returns else 0.0
        gross_profit = sum(value for value in closed_trade_returns if value > 0)
        gross_loss = abs(sum(value for value in closed_trade_returns if value < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        monthly_map: dict[str, float] = {}
        for idx in range(1, len(equity_curve)):
            month_key = equity_curve[idx]["date"][:7]
            prev_equity = float(equity_curve[idx - 1]["equity"])
            curr_equity = float(equity_curve[idx]["equity"])
            daily_ret = 0.0 if prev_equity == 0 else (curr_equity / prev_equity) - 1.0
            monthly_map[month_key] = (1.0 + monthly_map.get(month_key, 0.0)) * (1.0 + daily_ret) - 1.0

        monthly_return_table = [
            {"month": month, "return_pct": round(value * 100.0, 6)}
            for month, value in sorted(monthly_map.items())
        ]

        metrics = {
            "total_return_pct": round(total_return * 100.0, 6),
            "buy_hold_return_pct": round(buy_hold_return * 100.0, 6),
            "alpha_vs_buy_hold_pct": round(alpha_vs_buy_hold * 100.0, 6),
            "annualized_return_pct": round(annualized_return * 100.0, 6),
            "volatility_pct": round(volatility * 100.0, 6),
            "sharpe_ratio": round(sharpe_ratio, 6),
            "max_drawdown_pct": round(max_drawdown, 6),
            "exposure_pct": round((exposure_days / bars_used) * 100.0, 6),
            "total_trades": len(trades),
            "trade_win_rate_pct": round(trade_win_rate, 6),
            "profit_factor": round(profit_factor, 6) if profit_factor is not None else None,
            "start_equity": round(initial_capital, 6),
            "end_equity": round(equity, 6),
            "bars_used": bars_used,
        }

        summary = {
            "ticker": backtest_run.company.ticker,
            "strategy_type": backtest_run.strategy_type,
            "resolution": backtest_run.resolution,
            "start_date": backtest_run.start_date.isoformat(),
            "end_date": backtest_run.end_date.isoformat(),
            "initial_capital": str(backtest_run.initial_capital),
            "position_size": str(backtest_run.position_size),
            "commission_bps": str(backtest_run.commission_bps),
            "config": config_json,
        }

        with transaction.atomic():
            BacktestResult.objects.update_or_create(
                backtest_run=backtest_run,
                defaults={
                    "metrics_json": metrics,
                    "equity_curve_json": equity_curve,
                    "drawdown_curve_json": drawdown_curve,
                    "signal_curve_json": signal_curve,
                    "trades_json": trades,
                    "monthly_return_table_json": monthly_return_table,
                },
            )
            backtest_run.status = BacktestRun.STATUS_SUCCESS
            backtest_run.summary_json = summary
            backtest_run.error_payload_json = {}
            backtest_run.finished_at = django_timezone.now()
            backtest_run.save(
                update_fields=["status", "summary_json", "error_payload_json", "finished_at", "updated_at"]
            )

        return BacktestExecutionResult(
            backtest_run_id=str(backtest_run.id),
            ticker=backtest_run.company.ticker,
            metrics=metrics,
            summary=summary,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            signal_curve=signal_curve,
            trades=trades,
            monthly_return_table=monthly_return_table,
        )

    @transaction.atomic
    def mark_failed(self, *, backtest_run: BacktestRun, error: str) -> BacktestRun:
        backtest_run.status = BacktestRun.STATUS_FAILED
        backtest_run.error_payload_json = {"error": error}
        backtest_run.finished_at = django_timezone.now()
        backtest_run.save(update_fields=["status", "error_payload_json", "finished_at", "updated_at"])
        return backtest_run
    
class PortfolioBacktestService:
    def __init__(self) -> None:
        self.price_service = HistoricalPriceIngestionService()

    def run_portfolio_momentum(
        self,
        *,
        tickers: list[str],
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        lookback_window: int = 90,
        rebalance_days: int = 21,
        top_n: int = 3,
    ) -> dict[str, Any]:
        companies = list(Company.objects.filter(ticker__in=tickers).order_by("ticker"))
        if not companies:
            raise ValueError("No valid companies found for portfolio backtest.")

        series_map: dict[str, list[BacktestPriceBar]] = {}
        for company in companies:
            bars = self.price_service.ensure_daily_bars(
                company=company,
                start_date=start_date,
                end_date=end_date,
                use_stored_data=True,
            )
            if bars:
                series_map[company.ticker] = bars

        common_dates = sorted(
            set.intersection(*[
                {bar.start_at.date().isoformat() for bar in bars}
                for bars in series_map.values()
            ])
        ) if series_map else []

        if len(common_dates) <= lookback_window:
            raise ValueError("Not enough overlapping history for portfolio backtest.")

        price_lookup = {
            ticker: {bar.start_at.date().isoformat(): float(bar.close_price) for bar in bars}
            for ticker, bars in series_map.items()
        }

        equity = float(initial_capital)
        equity_curve = []
        weights: dict[str, float] = {}

        for idx, dt in enumerate(common_dates):
            if idx >= lookback_window and (idx - lookback_window) % rebalance_days == 0:
                momentum_scores = []
                for ticker in series_map.keys():
                    now_price = price_lookup[ticker][dt]
                    old_price = price_lookup[ticker][common_dates[idx - lookback_window]]
                    if old_price > 0:
                        momentum_scores.append((ticker, (now_price / old_price) - 1.0))
                momentum_scores.sort(key=lambda item: item[1], reverse=True)
                selected = momentum_scores[:top_n]
                weights = {ticker: (1.0 / len(selected)) for ticker, _ in selected} if selected else {}

            daily_return = 0.0
            if idx > 0 and weights:
                prev_dt = common_dates[idx - 1]
                for ticker, weight in weights.items():
                    prev_price = price_lookup[ticker][prev_dt]
                    now_price = price_lookup[ticker][dt]
                    if prev_price > 0:
                        daily_return += weight * ((now_price / prev_price) - 1.0)
                equity *= (1.0 + daily_return)

            equity_curve.append(
                {
                    "date": dt,
                    "equity": round(equity, 4),
                    "selected_tickers": sorted(weights.keys()),
                }
            )

        total_return_pct = ((equity / float(initial_capital)) - 1.0) * 100.0
        return {
            "strategy_type": "portfolio_momentum",
            "tickers": sorted(series_map.keys()),
            "metrics": {
                "total_return_pct": round(total_return_pct, 4),
                "end_equity": round(equity, 4),
                "start_equity": float(initial_capital),
                "bars_used": len(common_dates),
            },
            "equity_curve": equity_curve,
        }
    
@dataclass(slots=True)
class EngineOutput:
    rows: list[dict[str, Any]]
    equity_curve: list[dict[str, Any]]
    drawdown_curve: list[dict[str, Any]]
    signal_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    daily_returns: list[float]


class StrategySignalService:
    @staticmethod
    def build_details(
        *,
        strategy_type: str,
        rows: list[dict[str, Any]],
        config_json: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if strategy_type == "sma_crossover":
            return StrategyLibrary.sma_crossover_details(
                rows=rows,
                short_window=int(config_json["short_window"]),
                long_window=int(config_json["long_window"]),
            )

        if strategy_type == "support_resistance_rsi_volume":
            return StrategyLibrary.support_resistance_rsi_volume_details(
                rows=rows,
                support_window=int(config_json["support_window"]),
                resistance_window=int(config_json["resistance_window"]),
                rsi_window=int(config_json["rsi_window"]),
                rsi_buy=float(config_json["rsi_buy"]),
                rsi_sell=float(config_json["rsi_sell"]),
                volume_window=int(config_json["volume_window"]),
                volume_multiplier=float(config_json["volume_multiplier"]),
                buy_tolerance_pct=float(config_json["buy_tolerance_pct"]),
                sell_tolerance_pct=float(config_json["sell_tolerance_pct"]),
            )

        if strategy_type == "momentum":
            return StrategyLibrary.momentum_details(
                rows=rows,
                lookback_window=int(config_json["lookback_window"]),
                breakout_threshold_pct=float(config_json["breakout_threshold_pct"]),
                exit_lookback_window=int(config_json["exit_lookback_window"]),
            )

        if strategy_type == "mean_reversion":
            return StrategyLibrary.mean_reversion_details(
                rows=rows,
                mean_window=int(config_json["mean_window"]),
                std_window=int(config_json["std_window"]),
                z_entry=float(config_json["z_entry"]),
                z_exit=float(config_json["z_exit"]),
            )

        raise ValueError(f"Unsupported strategy_type '{strategy_type}'.")


class BacktestExecutionEngine:
    @staticmethod
    def run(
        *,
        rows: list[dict[str, Any]],
        details: list[dict[str, Any]],
        initial_capital: float,
        position_size: float,
        commission_rate: float,
    ) -> EngineOutput:
        equity = initial_capital
        peak_equity = initial_capital

        equity_curve: list[dict[str, Any]] = []
        drawdown_curve: list[dict[str, Any]] = []
        signal_curve: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        daily_returns: list[float] = []

        previous_position = 0
        previous_close = float(rows[0]["close"])
        entry_price = None
        entry_date = None

        for idx, row in enumerate(rows):
            detail = details[idx]
            target_position = int(detail["target_position"])
            current_close = float(row["close"])
            date_value = row["date"]

            if idx > 0:
                asset_return = (current_close / previous_close) - 1.0
                strategy_return = asset_return * previous_position * position_size

                trade_cost = 0.0
                if target_position != previous_position:
                    trade_cost = commission_rate * abs(target_position - previous_position) * position_size

                    trade_record = {
                        "date": date_value,
                        "action": detail["event"],
                        "price": round(current_close, 6),
                        "position_before": previous_position,
                        "position_after": target_position,
                        "estimated_cost_pct": round(trade_cost * 100.0, 6),
                        "reason": detail.get("reason", ""),
                    }

                    if target_position == 1 and previous_position == 0:
                        entry_price = current_close
                        entry_date = date_value

                    if target_position == 0 and previous_position == 1 and entry_price is not None:
                        trade_record["entry_date"] = entry_date
                        trade_record["trade_return_pct"] = round(((current_close / entry_price) - 1.0) * 100.0, 6)
                        entry_price = None
                        entry_date = None

                    trades.append(trade_record)

                net_return = strategy_return - trade_cost
                equity *= 1.0 + net_return
                daily_returns.append(net_return)

            peak_equity = max(peak_equity, equity)
            drawdown = 0.0 if peak_equity == 0 else (equity / peak_equity) - 1.0

            equity_curve.append(
                {
                    "date": date_value,
                    "equity": round(equity, 6),
                    "close": round(current_close, 6),
                    "position": previous_position,
                }
            )

            drawdown_curve.append(
                {
                    "date": date_value,
                    "drawdown_pct": round(drawdown * 100.0, 6),
                }
            )

            signal_curve.append(
                {
                    "date": date_value,
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    **detail,
                }
            )

            previous_position = target_position
            previous_close = current_close

        return EngineOutput(
            rows=rows,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            signal_curve=signal_curve,
            trades=trades,
            daily_returns=daily_returns,
        )


class BacktestEvaluationService:
    @staticmethod
    def evaluate(
        *,
        rows: list[dict[str, Any]],
        equity_curve: list[dict[str, Any]],
        drawdown_curve: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        daily_returns: list[float],
        initial_capital: float,
    ) -> dict[str, Any]:
        end_equity = float(equity_curve[-1]["equity"]) if equity_curve else initial_capital
        total_return_pct = ((end_equity / initial_capital) - 1.0) * 100.0 if initial_capital else 0.0

        closes = [float(r["close"]) for r in rows]
        buy_hold_return_pct = ((closes[-1] / closes[0]) - 1.0) * 100.0 if len(closes) >= 2 and closes[0] else 0.0
        alpha_vs_buy_hold_pct = total_return_pct - buy_hold_return_pct

        n = len(daily_returns)
        annualized_return_pct = (((end_equity / initial_capital) ** (252 / max(n, 1))) - 1.0) * 100.0 if n > 0 and initial_capital else 0.0
        volatility_pct = pstdev(daily_returns) * sqrt(252) * 100.0 if len(daily_returns) > 1 else 0.0
        mean_daily = (sum(daily_returns) / len(daily_returns)) if daily_returns else 0.0
        sharpe_ratio = ((mean_daily * 252) / (pstdev(daily_returns) * sqrt(252))) if len(daily_returns) > 1 and pstdev(daily_returns) > 0 else 0.0
        max_drawdown_pct = min((point["drawdown_pct"] for point in drawdown_curve), default=0.0)

        closed_trade_returns = [
            float(t["trade_return_pct"])
            for t in trades
            if t.get("trade_return_pct") is not None
        ]
        winning = [x for x in closed_trade_returns if x > 0]
        losing = [x for x in closed_trade_returns if x < 0]

        win_rate = (len(winning) / len(closed_trade_returns) * 100.0) if closed_trade_returns else 0.0
        avg_win = (sum(winning) / len(winning)) if winning else 0.0
        avg_loss = (sum(losing) / len(losing)) if losing else 0.0
        profit_factor = (sum(winning) / abs(sum(losing))) if losing and sum(losing) != 0 else None

        return {
            "overview": {
                "bars_used": len(rows),
                "start_equity": round(initial_capital, 6),
                "end_equity": round(end_equity, 6),
                "total_return_pct": round(total_return_pct, 6),
                "buy_hold_return_pct": round(buy_hold_return_pct, 6),
                "alpha_vs_buy_hold_pct": round(alpha_vs_buy_hold_pct, 6),
            },
            "performance": {
                "annualized_return_pct": round(annualized_return_pct, 6),
                "volatility_pct": round(volatility_pct, 6),
                "sharpe_ratio": round(sharpe_ratio, 6),
            },
            "risk": {
                "max_drawdown_pct": round(max_drawdown_pct, 6),
            },
            "trade_analysis": {
                "total_trades": len(trades),
                "closed_trades": len(closed_trade_returns),
                "trade_win_rate_pct": round(win_rate, 6),
                "avg_win_pct": round(avg_win, 6),
                "avg_loss_pct": round(avg_loss, 6),
                "profit_factor": round(profit_factor, 6) if profit_factor is not None else None,
            },
            "diagnostics": {
                "signal_points": len(rows),
                "equity_points": len(equity_curve),
                "drawdown_points": len(drawdown_curve),
            },
        }