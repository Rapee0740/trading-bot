# ============================================================
# backtester.py - ระบบ Backtesting สำหรับ Gold Trading Bot
# ============================================================

import argparse
import csv
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import config
from utils import (
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_position_size,
    calculate_rsi,
    pip_to_price,
)


# ------------------------------------
# Data Classes
# ------------------------------------

@dataclass
class Trade:
    """ข้อมูลการเทรดแต่ละครั้ง"""
    entry_time: datetime
    exit_time: datetime = None
    direction: str = ""          # "BUY" หรือ "SELL"
    entry_price: float = 0.0
    exit_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    lot: float = 0.01
    profit: float = 0.0
    profit_pips: float = 0.0
    exit_reason: str = ""        # "TP", "SL", "SIGNAL", "END"
    is_winner: bool = False


@dataclass
class BacktestResult:
    """ผลลัพธ์การ Backtest ทั้งหมด"""
    symbol: str = ""
    timeframe: str = ""
    period_start: str = ""
    period_end: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    total_profit_pips: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_duration: str = ""
    risk_reward_ratio: float = 0.0
    sharpe_ratio: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


# ------------------------------------
# Backtester Class
# ------------------------------------

class Backtester:
    """ระบบ Backtesting สำหรับทดสอบกลยุทธ์"""

    def __init__(self, initial_balance: float = 10000.0) -> None:
        self.initial_balance = initial_balance
        self.balance = initial_balance

    def connect_mt5(self) -> bool:
        """
        เชื่อมต่อ MT5 เพื่อดึงข้อมูลประวัติ

        Returns:
            bool: True ถ้าเชื่อมต่อสำเร็จ
        """
        if mt5 is None:
            print("❌ ไม่พบ MetaTrader5 package กรุณา pip install MetaTrader5")
            return False

        if not mt5.initialize(path=config.MT5_PATH):
            print(f"❌ เริ่มต้น MT5 ไม่สำเร็จ: {mt5.last_error()}")
            return False

        if not mt5.login(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        ):
            print(f"❌ Login MT5 ไม่สำเร็จ: {mt5.last_error()}")
            mt5.shutdown()
            return False

        print("✅ เชื่อมต่อ MT5 สำเร็จ")
        return True

    def get_historical_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame | None:
        """
        ดึงข้อมูลประวัติราคาจาก MT5

        Args:
            start_date: วันที่เริ่มต้น
            end_date: วันที่สิ้นสุด

        Returns:
            pd.DataFrame | None: ข้อมูลราคา หรือ None ถ้าเกิดข้อผิดพลาด
        """
        if mt5 is None:
            return None

        # แปลง Timeframe string เป็น MT5 constant
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1,
        }

        timeframe_const = timeframe_map.get(config.TIMEFRAME)
        if timeframe_const is None:
            print(f"❌ Timeframe ไม่ถูกต้อง: {config.TIMEFRAME}")
            return None

        # ดึงข้อมูลช่วงวันที่ที่กำหนด
        rates = mt5.copy_rates_range(config.SYMBOL, timeframe_const, start_date, end_date)
        if rates is None or len(rates) == 0:
            print(f"❌ ดึงข้อมูลประวัติไม่สำเร็จ: {mt5.last_error()}")
            return None

        # แปลงเป็น DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        print(f"✅ ดึงข้อมูล {len(df)} แท่งเทียน ({start_date.date()} ถึง {end_date.date()})")
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        สร้างสัญญาณการเทรดสำหรับแต่ละแท่งเทียน

        Args:
            df: ข้อมูลราคา

        Returns:
            pd.DataFrame: DataFrame พร้อมคอลัมน์ indicators และ signal
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # คำนวณ Indicators
        df = df.copy()
        df["ema_fast"] = calculate_ema(close, config.EMA_FAST_PERIOD)
        df["ema_slow"] = calculate_ema(close, config.EMA_SLOW_PERIOD)
        df["rsi"] = calculate_rsi(close, config.RSI_PERIOD)
        _, _, macd_hist = calculate_macd(close, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
        df["macd_hist"] = macd_hist
        df["atr"] = calculate_atr(high, low, close)

        # สร้างสัญญาณสำหรับแต่ละแท่งเทียน
        signals = []
        for i in range(len(df)):
            if i < 2:
                signals.append("NEUTRAL")
                continue

            buy_score = 0
            sell_score = 0

            curr_ema_fast = df["ema_fast"].iloc[i]
            curr_ema_slow = df["ema_slow"].iloc[i]
            prev_ema_fast = df["ema_fast"].iloc[i - 1]
            prev_ema_slow = df["ema_slow"].iloc[i - 1]
            curr_rsi = df["rsi"].iloc[i]
            curr_macd_hist = df["macd_hist"].iloc[i]
            prev_macd_hist = df["macd_hist"].iloc[i - 1]

            # EMA Crossover (3 คะแนน)
            if (curr_ema_fast > curr_ema_slow) and (prev_ema_fast <= prev_ema_slow):
                buy_score += 3
            elif (curr_ema_fast < curr_ema_slow) and (prev_ema_fast >= prev_ema_slow):
                sell_score += 3

            # EMA Trend (1 คะแนน)
            if curr_ema_fast > curr_ema_slow:
                buy_score += 1
            else:
                sell_score += 1

            # RSI Oversold/Overbought (2 คะแนน)
            if curr_rsi <= config.RSI_OVERSOLD:
                buy_score += 2
            elif curr_rsi >= config.RSI_OVERBOUGHT:
                sell_score += 2

            # RSI ต่ำกว่า/สูงกว่า 50 (1 คะแนน)
            if curr_rsi < 50:
                sell_score += 1
            else:
                buy_score += 1

            # MACD Crossover (2 คะแนน)
            if (curr_macd_hist > 0) and (prev_macd_hist <= 0):
                buy_score += 2
            elif (curr_macd_hist < 0) and (prev_macd_hist >= 0):
                sell_score += 2

            # MACD Direction (1 คะแนน)
            if curr_macd_hist > 0:
                buy_score += 1
            else:
                sell_score += 1

            # ตัดสินใจสัญญาณ
            if buy_score >= 4 and buy_score > sell_score:
                signals.append("BUY")
            elif sell_score >= 4 and sell_score > buy_score:
                signals.append("SELL")
            else:
                signals.append("NEUTRAL")

        df["signal"] = signals
        return df

    def simulate_trade_exit(self, trade: Trade, candle: pd.Series) -> bool:
        """
        จำลองการปิด Trade เมื่อถึง SL หรือ TP

        Args:
            trade: ข้อมูล Trade ที่เปิดอยู่
            candle: ข้อมูลแท่งเทียนปัจจุบัน

        Returns:
            bool: True ถ้า Trade ถูกปิดในแท่งเทียนนี้
        """
        high = candle["high"]
        low = candle["low"]

        # 0.01 คือขนาด 1 pip สำหรับ XAUUSD (Gold pip = $0.01 per point)
        xauusd_pip_size = 0.01

        if trade.direction == "BUY":
            # ตรวจสอบ Stop Loss
            if low <= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_reason = "SL"
                trade.profit_pips = (trade.sl - trade.entry_price) / xauusd_pip_size
                trade.profit = trade.profit_pips * 100 * trade.lot
                trade.is_winner = False
                return True

            # ตรวจสอบ Take Profit
            if high >= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_reason = "TP"
                trade.profit_pips = (trade.tp - trade.entry_price) / xauusd_pip_size
                trade.profit = trade.profit_pips * 100 * trade.lot
                trade.is_winner = True
                return True

        elif trade.direction == "SELL":
            # ตรวจสอบ Stop Loss
            if high >= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_reason = "SL"
                trade.profit_pips = (trade.entry_price - trade.sl) / xauusd_pip_size
                trade.profit = trade.profit_pips * 100 * trade.lot
                trade.is_winner = False
                return True

            # ตรวจสอบ Take Profit
            if low <= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_reason = "TP"
                trade.profit_pips = (trade.entry_price - trade.tp) / xauusd_pip_size
                trade.profit = trade.profit_pips * 100 * trade.lot
                trade.is_winner = True
                return True

        return False

    def run_backtest(self, df: pd.DataFrame) -> BacktestResult:
        """
        รันการ Backtest ผ่านข้อมูลทั้งหมด

        Args:
            df: DataFrame ที่มีข้อมูลราคาและสัญญาณ

        Returns:
            BacktestResult: ผลลัพธ์การ Backtest
        """
        # สร้างสัญญาณสำหรับทุกแท่งเทียน
        df = self.generate_signals(df)

        trades: list[Trade] = []
        equity_curve: list[float] = [self.initial_balance]
        current_balance = self.initial_balance
        open_trade: Trade | None = None

        # วนลูปผ่านแท่งเทียนทุกอัน
        for i in range(len(df)):
            candle = df.iloc[i]
            candle_time = df.index[i]

            # ตรวจสอบ Trade ที่เปิดอยู่
            if open_trade is not None:
                # ตรวจสอบว่าถึง SL/TP หรือยัง
                if self.simulate_trade_exit(open_trade, candle):
                    open_trade.exit_time = candle_time
                    current_balance += open_trade.profit
                    trades.append(open_trade)
                    equity_curve.append(current_balance)
                    open_trade = None
                    continue

                # ตรวจสอบสัญญาณกลับทิศ (Reverse Signal Exit)
                current_signal = candle["signal"]
                if (open_trade.direction == "BUY" and current_signal == "SELL") or \
                   (open_trade.direction == "SELL" and current_signal == "BUY"):
                    # ปิด Trade ตามราคาปิดแท่งเทียน
                    open_trade.exit_price = candle["close"]
                    open_trade.exit_time = candle_time
                    open_trade.exit_reason = "SIGNAL"

                    # 0.01 = ขนาด 1 pip สำหรับ XAUUSD
                    xauusd_pip_size = 0.01
                    if open_trade.direction == "BUY":
                        open_trade.profit_pips = (open_trade.exit_price - open_trade.entry_price) / xauusd_pip_size
                    else:
                        open_trade.profit_pips = (open_trade.entry_price - open_trade.exit_price) / xauusd_pip_size

                    open_trade.profit = open_trade.profit_pips * 100 * open_trade.lot
                    open_trade.is_winner = open_trade.profit > 0

                    current_balance += open_trade.profit
                    trades.append(open_trade)
                    equity_curve.append(current_balance)
                    open_trade = None
                    # ไม่ continue เพื่อให้เปิด Trade ใหม่ตามสัญญาณ

            # เปิด Trade ใหม่ถ้ายังไม่มี Trade เปิดอยู่
            if open_trade is None:
                signal = candle["signal"]
                if signal in ("BUY", "SELL"):
                    entry_price = candle["close"]
                    sl_distance = pip_to_price(config.STOP_LOSS_PIPS, config.SYMBOL)
                    tp_distance = pip_to_price(config.TAKE_PROFIT_PIPS, config.SYMBOL)

                    if signal == "BUY":
                        sl = entry_price - sl_distance
                        tp = entry_price + tp_distance
                    else:
                        sl = entry_price + sl_distance
                        tp = entry_price - tp_distance

                    # คำนวณขนาด Lot
                    lot = calculate_position_size(current_balance, config.RISK_PERCENT, config.STOP_LOSS_PIPS)

                    open_trade = Trade(
                        entry_time=candle_time,
                        direction=signal,
                        entry_price=entry_price,
                        sl=sl,
                        tp=tp,
                        lot=lot,
                    )

        # ปิด Trade ที่ยังเหลืออยู่เมื่อสิ้นสุดการทดสอบ
        if open_trade is not None:
            last_candle = df.iloc[-1]
            open_trade.exit_price = last_candle["close"]
            open_trade.exit_time = df.index[-1]
            open_trade.exit_reason = "END"

            # 0.01 = ขนาด 1 pip สำหรับ XAUUSD
            xauusd_pip_size = 0.01
            if open_trade.direction == "BUY":
                open_trade.profit_pips = (open_trade.exit_price - open_trade.entry_price) / xauusd_pip_size
            else:
                open_trade.profit_pips = (open_trade.entry_price - open_trade.exit_price) / xauusd_pip_size

            open_trade.profit = open_trade.profit_pips * 100 * open_trade.lot
            open_trade.is_winner = open_trade.profit > 0
            current_balance += open_trade.profit
            trades.append(open_trade)
            equity_curve.append(current_balance)

        # คำนวณผลลัพธ์
        result = self._calculate_results(df, trades, equity_curve)
        return result

    def _calculate_results(
        self,
        df: pd.DataFrame,
        trades: list[Trade],
        equity_curve: list[float],
    ) -> BacktestResult:
        """
        คำนวณสถิติทั้งหมดจากผลการเทรด

        Args:
            df: DataFrame ข้อมูลราคา
            trades: รายการ trades ทั้งหมด
            equity_curve: เส้นกราฟ equity

        Returns:
            BacktestResult: ผลลัพธ์การ Backtest พร้อมสถิติ
        """
        result = BacktestResult(
            symbol=config.SYMBOL,
            timeframe=config.TIMEFRAME,
            period_start=str(df.index[0].date()) if len(df) > 0 else "",
            period_end=str(df.index[-1].date()) if len(df) > 0 else "",
            trades=trades,
            equity_curve=equity_curve,
        )

        if not trades:
            return result

        # สถิติพื้นฐาน
        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t.is_winner)
        result.losing_trades = result.total_trades - result.winning_trades

        # Win Rate
        result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0.0

        # Profit/Loss
        result.total_profit = sum(t.profit for t in trades)
        result.total_profit_pips = sum(t.profit_pips for t in trades)
        result.gross_profit = sum(t.profit for t in trades if t.profit > 0)
        result.gross_loss = abs(sum(t.profit for t in trades if t.profit < 0))

        # Profit Factor
        result.profit_factor = (result.gross_profit / result.gross_loss) if result.gross_loss > 0 else float("inf")

        # Average Win/Loss
        winning = [t.profit for t in trades if t.is_winner]
        losing = [t.profit for t in trades if not t.is_winner]
        result.avg_win = (sum(winning) / len(winning)) if winning else 0.0
        result.avg_loss = (sum(losing) / len(losing)) if losing else 0.0

        # Best/Worst Trade
        result.best_trade = max(t.profit for t in trades)
        result.worst_trade = min(t.profit for t in trades)

        # Max Drawdown (คำนวณจาก equity curve)
        peak_equity = self.initial_balance
        max_dd = 0.0
        max_dd_pct = 0.0
        for eq in equity_curve:
            if eq > peak_equity:
                peak_equity = eq
            dd = peak_equity - eq
            dd_pct = (dd / peak_equity * 100) if peak_equity > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        result.max_drawdown = max_dd
        result.max_drawdown_pct = max_dd_pct

        # Risk/Reward Ratio
        result.risk_reward_ratio = abs(result.avg_win / result.avg_loss) if result.avg_loss != 0 else 0.0

        # Average Trade Duration
        durations = []
        for t in trades:
            if t.entry_time and t.exit_time:
                duration = t.exit_time - t.entry_time
                durations.append(duration.total_seconds())

        if durations:
            avg_seconds = sum(durations) / len(durations)
            avg_hours = int(avg_seconds // 3600)
            avg_minutes = int((avg_seconds % 3600) // 60)
            result.avg_trade_duration = f"{avg_hours}h {avg_minutes}m"

        # Sharpe Ratio annualized ด้วย sqrt(252) = จำนวนวันเทรดต่อปี (252 trading days per year)
        profits = [t.profit for t in trades]
        if len(profits) > 1:
            avg_profit = sum(profits) / len(profits)
            variance = sum((p - avg_profit) ** 2 for p in profits) / (len(profits) - 1)
            std_profit = math.sqrt(variance) if variance > 0 else 0.0
            if std_profit > 0:
                result.sharpe_ratio = (avg_profit / std_profit) * math.sqrt(252)

        return result

    @staticmethod
    def print_results(result: BacktestResult) -> None:
        """
        แสดงผลลัพธ์การ Backtest ในรูปแบบที่สวยงาม

        Args:
            result: ผลลัพธ์การ Backtest
        """
        print("\n" + "=" * 60)
        print("📊 ผลลัพธ์การ BACKTEST")
        print("=" * 60)
        print(f"  Symbol     : {result.symbol}")
        print(f"  Timeframe  : {result.timeframe}")
        print(f"  Period     : {result.period_start} → {result.period_end}")
        print("-" * 60)
        print(f"  Total Trades   : {result.total_trades}")
        print(f"  Winning Trades : {result.winning_trades} 🟢")
        print(f"  Losing Trades  : {result.losing_trades} 🔴")
        print(f"  Win Rate       : {result.win_rate:.1f}%")
        print("-" * 60)
        print(f"  Total Profit   : {result.total_profit:+.2f} USD")
        print(f"  Total Pips     : {result.total_profit_pips:+.1f} pips")
        print(f"  Gross Profit   : {result.gross_profit:.2f} USD")
        print(f"  Gross Loss     : -{result.gross_loss:.2f} USD")
        print(f"  Profit Factor  : {result.profit_factor:.2f}")
        print("-" * 60)
        print(f"  Max Drawdown   : {result.max_drawdown:.2f} USD ({result.max_drawdown_pct:.1f}%)")
        print(f"  Avg Win        : {result.avg_win:+.2f} USD")
        print(f"  Avg Loss       : {result.avg_loss:+.2f} USD")
        print(f"  Best Trade     : {result.best_trade:+.2f} USD")
        print(f"  Worst Trade    : {result.worst_trade:+.2f} USD")
        print("-" * 60)
        print(f"  Risk/Reward    : 1:{result.risk_reward_ratio:.2f}")
        print(f"  Sharpe Ratio   : {result.sharpe_ratio:.2f}")
        print(f"  Avg Duration   : {result.avg_trade_duration}")
        print("=" * 60)

        # Exit Reasons Breakdown
        if result.trades:
            reasons: dict[str, int] = {}
            for t in result.trades:
                reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

            print("\n📋 สาเหตุการปิด Trade:")
            reason_emoji = {"TP": "🎯", "SL": "🛑", "SIGNAL": "🔄", "END": "⏹️"}
            for reason, count in sorted(reasons.items()):
                emoji = reason_emoji.get(reason, "❓")
                pct = count / result.total_trades * 100 if result.total_trades > 0 else 0
                print(f"  {emoji} {reason:8s} : {count:4d} ({pct:.1f}%)")

        # Monthly Breakdown
        if result.trades:
            print("\n📅 สรุปรายเดือน:")
            print(f"  {'เดือน':12s} | {'Trades':6s} | {'Win%':5s} | {'Profit':10s}")
            print("  " + "-" * 42)

            # จัดกลุ่มตามเดือน
            monthly: dict[str, dict] = {}
            for t in result.trades:
                if t.entry_time:
                    month_key = t.entry_time.strftime("%Y-%m")
                    if month_key not in monthly:
                        monthly[month_key] = {"trades": 0, "wins": 0, "profit": 0.0}
                    monthly[month_key]["trades"] += 1
                    if t.is_winner:
                        monthly[month_key]["wins"] += 1
                    monthly[month_key]["profit"] += t.profit

            for month, stats in sorted(monthly.items()):
                win_pct = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0.0
                profit_emoji = "🟢" if stats["profit"] >= 0 else "🔴"
                print(
                    f"  {month:12s} | {stats['trades']:6d} | {win_pct:4.1f}% | "
                    f"{profit_emoji} {stats['profit']:+.2f}"
                )

        print("=" * 60)

    @staticmethod
    def export_trades_csv(result: BacktestResult, filename: str) -> None:
        """
        Export ข้อมูล trades เป็นไฟล์ CSV

        Args:
            result: ผลลัพธ์การ Backtest
            filename: ชื่อไฟล์ CSV
        """
        if not result.trades:
            print("⚠️ ไม่มีข้อมูล trades ที่จะ export")
            return

        fieldnames = [
            "entry_time", "exit_time", "direction", "entry_price", "exit_price",
            "sl", "tp", "lot", "profit", "profit_pips", "exit_reason", "is_winner",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for trade in result.trades:
                writer.writerow({
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "direction": trade.direction,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "sl": trade.sl,
                    "tp": trade.tp,
                    "lot": trade.lot,
                    "profit": round(trade.profit, 2),
                    "profit_pips": round(trade.profit_pips, 1),
                    "exit_reason": trade.exit_reason,
                    "is_winner": trade.is_winner,
                })

        print(f"✅ Export สำเร็จ: {filename} ({len(result.trades)} trades)")


# ------------------------------------
# Main Function
# ------------------------------------

def main() -> None:
    """Entry point สำหรับรัน Backtest จาก command line"""
    parser = argparse.ArgumentParser(
        description="🤖 Gold Trading Bot Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  python backtester.py
  python backtester.py --days 180
  python backtester.py --start 2025-01-01 --end 2026-03-01
  python backtester.py --days 365 --balance 5000 --export
        """,
    )

    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="จำนวนวันย้อนหลังที่ต้องการทดสอบ (default: 365)",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="วันที่เริ่มต้น (รูปแบบ: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="วันที่สิ้นสุด (รูปแบบ: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=10000.0,
        help="ยอดเงินเริ่มต้น (default: 10000)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export ผลการเทรดเป็นไฟล์ CSV",
    )

    args = parser.parse_args()

    # กำหนดช่วงวันที่
    now = datetime.now(tz=timezone.utc)

    if args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_date = now
        start_date = end_date - timedelta(days=args.days)

    print("=" * 60)
    print("🤖 Gold Trading Bot - Backtester")
    print("=" * 60)
    print(f"  Symbol    : {config.SYMBOL}")
    print(f"  Timeframe : {config.TIMEFRAME}")
    print(f"  Period    : {start_date.date()} → {end_date.date()}")
    print(f"  Balance   : {args.balance:.2f} USD")
    print("=" * 60)

    # สร้าง Backtester
    backtester = Backtester(initial_balance=args.balance)

    # เชื่อมต่อ MT5 และดึงข้อมูล
    if not backtester.connect_mt5():
        print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
        return

    df = backtester.get_historical_data(start_date, end_date)
    if df is None:
        print("❌ ไม่สามารถดึงข้อมูลประวัติได้")
        if mt5 is not None:
            mt5.shutdown()
        return

    # รัน Backtest
    print("\n⏳ กำลังรัน Backtest...")
    result = backtester.run_backtest(df)

    # แสดงผลลัพธ์
    Backtester.print_results(result)

    # Export CSV ถ้าต้องการ
    if args.export:
        filename = f"backtest_{config.SYMBOL}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        Backtester.export_trades_csv(result, filename)

    # ตัดการเชื่อมต่อ MT5
    if mt5 is not None:
        mt5.shutdown()


# ------------------------------------
# Entry Point
# ------------------------------------
if __name__ == "__main__":
    main()
