# ============================================================
# gold_trading_bot.py - บอทเทรดทองคำอัตโนมัติสำหรับ MetaTrader 5
# ============================================================

import logging
import time
from datetime import datetime, timezone

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # ใช้ในกรณีทดสอบโดยไม่มี MT5

import config
from utils import (
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_position_size,
    calculate_rsi,
    format_signal_message,
    pip_to_price,
)

# ------------------------------------
# Timeframe Mapping (แปลง string เป็น MT5 constant)
# ------------------------------------
TIMEFRAME_MAP: dict = {
    "M1": None,
    "M5": None,
    "M15": None,
    "M30": None,
    "H1": None,
    "H4": None,
    "D1": None,
    "W1": None,
    "MN1": None,
}

# กำหนดค่า MT5 constants เมื่อ import สำเร็จ
if mt5 is not None:
    TIMEFRAME_MAP = {
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


class GoldTradingBot:
    """บอทเทรดทองคำอัตโนมัติสำหรับ MetaTrader 5"""

    def __init__(
        self,
        symbol: str = config.SYMBOL,
        timeframe: str = config.TIMEFRAME,
        magic_number: int = config.MAGIC_NUMBER,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = magic_number

        # สถิติรายวัน
        self.daily_loss: float = 0.0
        self.trades_today: int = 0
        self.last_trade_date: datetime | None = None

        # ตั้งค่า Logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """ตั้งค่าระบบ Logging สำหรับบอท"""
        log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
        self.logger = logging.getLogger("GoldTradingBot")
        self.logger.setLevel(logging.DEBUG)

        # ป้องกันการเพิ่ม handler ซ้ำ
        if self.logger.handlers:
            return

        # File handler (บันทึกทุก level ตั้งแต่ DEBUG)
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Console handler (แสดงเฉพาะ INFO ขึ้นไป)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def connect_mt5(self) -> bool:
        """
        เชื่อมต่อกับ MetaTrader 5

        Returns:
            bool: True ถ้าเชื่อมต่อสำเร็จ
        """
        if mt5 is None:
            self.logger.error("❌ ไม่พบ MetaTrader5 package กรุณา pip install MetaTrader5")
            return False

        # เริ่มต้น MT5
        if not mt5.initialize(path=config.MT5_PATH):
            self.logger.error(f"❌ เริ่มต้น MT5 ไม่สำเร็จ: {mt5.last_error()}")
            return False

        # Login เข้าบัญชี
        if not mt5.login(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        ):
            self.logger.error(f"❌ Login MT5 ไม่สำเร็จ: {mt5.last_error()}")
            mt5.shutdown()
            return False

        # แสดงข้อมูลบัญชี
        account_info = mt5.account_info()
        if account_info:
            self.logger.info("✅ เชื่อมต่อ MT5 สำเร็จ")
            self.logger.info(f"   💰 Balance  : {account_info.balance:.2f} {account_info.currency}")
            self.logger.info(f"   📊 Equity   : {account_info.equity:.2f} {account_info.currency}")
            self.logger.info(f"   🖥️  Server   : {account_info.server}")
            self.logger.info(f"   📈 Leverage : 1:{account_info.leverage}")

        return True

    def disconnect_mt5(self) -> None:
        """ตัดการเชื่อมต่อ MT5"""
        if mt5 is not None:
            mt5.shutdown()
            self.logger.info("🔌 ตัดการเชื่อมต่อ MT5 แล้ว")

    def get_market_data(self, num_candles: int = 200) -> pd.DataFrame | None:
        """
        ดึงข้อมูลตลาดจาก MT5

        Args:
            num_candles: จำนวนแท่งเทียนที่ต้องการ

        Returns:
            pd.DataFrame | None: ข้อมูลราคา หรือ None ถ้าเกิดข้อผิดพลาด
        """
        if mt5 is None:
            return None

        timeframe_const = TIMEFRAME_MAP.get(self.timeframe)
        if timeframe_const is None:
            self.logger.error(f"❌ Timeframe ไม่ถูกต้อง: {self.timeframe}")
            return None

        # ดึงข้อมูลจาก MT5
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe_const, 0, num_candles)
        if rates is None or len(rates) == 0:
            self.logger.error(f"❌ ดึงข้อมูลตลาดไม่สำเร็จ: {mt5.last_error()}")
            return None

        # แปลงเป็น DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        return df

    def get_current_price(self) -> dict | None:
        """
        ดึงราคาปัจจุบัน

        Returns:
            dict | None: ข้อมูลราคาปัจจุบัน หรือ None ถ้าเกิดข้อผิดพลาด
        """
        if mt5 is None:
            return None

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error(f"❌ ดึงราคาปัจจุบันไม่สำเร็จ: {mt5.last_error()}")
            return None

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 5),
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
        }

    def analyze_market(self, df: pd.DataFrame) -> dict:
        """
        วิเคราะห์ตลาดด้วย Technical Indicators

        Args:
            df: ข้อมูลราคา DataFrame

        Returns:
            dict: ผลการวิเคราะห์และสัญญาณ
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # คำนวณ Indicators
        ema_fast = calculate_ema(close, config.EMA_FAST_PERIOD)
        ema_slow = calculate_ema(close, config.EMA_SLOW_PERIOD)
        rsi = calculate_rsi(close, config.RSI_PERIOD)
        _, _, macd_hist = calculate_macd(close, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
        atr = calculate_atr(high, low, close)

        # ค่าปัจจุบันและก่อนหน้า
        curr_ema_fast = ema_fast.iloc[-1]
        curr_ema_slow = ema_slow.iloc[-1]
        prev_ema_fast = ema_fast.iloc[-2]
        prev_ema_slow = ema_slow.iloc[-2]

        curr_rsi = rsi.iloc[-1]
        curr_macd_hist = macd_hist.iloc[-1]
        prev_macd_hist = macd_hist.iloc[-2]

        current_close = close.iloc[-1]
        current_atr = atr.iloc[-1]

        # ------------------------------------
        # ระบบคะแนน (Scoring System)
        # ------------------------------------
        buy_score = 0
        sell_score = 0
        reasons = []

        # EMA Crossover (3 คะแนน)
        ema_bull_cross = (curr_ema_fast > curr_ema_slow) and (prev_ema_fast <= prev_ema_slow)
        ema_bear_cross = (curr_ema_fast < curr_ema_slow) and (prev_ema_fast >= prev_ema_slow)

        if ema_bull_cross:
            buy_score += 3
            reasons.append("📈 EMA Bullish Crossover (+3)")
        elif ema_bear_cross:
            sell_score += 3
            reasons.append("📉 EMA Bearish Crossover (+3)")

        # EMA Trend Direction (1 คะแนน)
        if curr_ema_fast > curr_ema_slow:
            buy_score += 1
            reasons.append("📊 EMA Uptrend (+1)")
        else:
            sell_score += 1
            reasons.append("📊 EMA Downtrend (+1)")

        # RSI Oversold/Overbought (2 คะแนน)
        if curr_rsi <= config.RSI_OVERSOLD:
            buy_score += 2
            reasons.append(f"💚 RSI Oversold {curr_rsi:.1f} (+2)")
        elif curr_rsi >= config.RSI_OVERBOUGHT:
            sell_score += 2
            reasons.append(f"❤️ RSI Overbought {curr_rsi:.1f} (+2)")

        # RSI ต่ำกว่า/สูงกว่า 50 (1 คะแนน)
        if curr_rsi < 50:
            sell_score += 1
            reasons.append(f"📉 RSI < 50 ({curr_rsi:.1f}) (+1)")
        else:
            buy_score += 1
            reasons.append(f"📈 RSI > 50 ({curr_rsi:.1f}) (+1)")

        # MACD Histogram Crossover (2 คะแนน) - เปลี่ยนทิศทาง
        macd_bull_cross = (curr_macd_hist > 0) and (prev_macd_hist <= 0)
        macd_bear_cross = (curr_macd_hist < 0) and (prev_macd_hist >= 0)

        if macd_bull_cross:
            buy_score += 2
            reasons.append("⬆️ MACD Bullish Cross (+2)")
        elif macd_bear_cross:
            sell_score += 2
            reasons.append("⬇️ MACD Bearish Cross (+2)")

        # MACD Direction (1 คะแนน)
        if curr_macd_hist > 0:
            buy_score += 1
            reasons.append("📊 MACD Positive (+1)")
        else:
            sell_score += 1
            reasons.append("📊 MACD Negative (+1)")

        # ------------------------------------
        # ตัดสินใจสัญญาณ
        # ------------------------------------
        signal = "NEUTRAL"
        if buy_score >= 4 and buy_score > sell_score:
            signal = "BUY"
        elif sell_score >= 4 and sell_score > buy_score:
            signal = "SELL"

        return {
            "signal": signal,
            "reasons": reasons,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "ema_fast": curr_ema_fast,
            "ema_slow": curr_ema_slow,
            "rsi": curr_rsi,
            "macd_histogram": curr_macd_hist,
            "atr": current_atr,
            "current_close": current_close,
        }

    def get_open_positions(self) -> list:
        """
        ดึงรายการ Position ที่เปิดอยู่ (กรองตาม Magic Number)

        Returns:
            list: รายการ positions
        """
        if mt5 is None:
            return []

        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []

        # กรองเฉพาะ positions ของบอทนี้
        return [p for p in positions if p.magic == self.magic_number]

    def open_trade(self, signal: str, analysis: dict) -> bool:
        """
        เปิด Order ใหม่

        Args:
            signal: ทิศทาง "BUY" หรือ "SELL"
            analysis: ผลการวิเคราะห์ตลาด

        Returns:
            bool: True ถ้าเปิด Order สำเร็จ
        """
        if mt5 is None:
            return False

        # ตรวจสอบจำนวน positions ที่เปิดอยู่
        open_positions = self.get_open_positions()
        if len(open_positions) >= config.MAX_POSITIONS:
            self.logger.warning(f"⚠️ เปิด Position ครบแล้ว ({config.MAX_POSITIONS} positions)")
            return False

        # ตรวจสอบ Daily Loss Limit
        if self.daily_loss >= config.MAX_DAILY_LOSS:
            self.logger.warning(f"⚠️ ถึงขีดจำกัด Daily Loss ({self.daily_loss:.2f} USD)")
            return False

        # ดึงราคาปัจจุบัน
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error("❌ ดึงราคาปัจจุบันไม่สำเร็จ")
            return False

        # ใช้ Ask สำหรับ BUY, Bid สำหรับ SELL
        price = tick.ask if signal == "BUY" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

        # ตรวจสอบและเปิดใช้งาน Symbol
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error(f"❌ ไม่พบข้อมูล Symbol: {self.symbol}")
            return False

        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                self.logger.error(f"❌ เปิดใช้งาน Symbol ไม่สำเร็จ: {self.symbol}")
                return False

        # คำนวณขนาด Lot
        account_info = mt5.account_info()
        # ใช้ค่าสำรองถ้าดึง account info ไม่ได้ (ป้องกัน error)
        balance = account_info.balance if account_info else 10000.0
        lot = calculate_position_size(balance, config.RISK_PERCENT, config.STOP_LOSS_PIPS)

        # คำนวณ SL และ TP
        sl_distance = pip_to_price(config.STOP_LOSS_PIPS, self.symbol)
        tp_distance = pip_to_price(config.TAKE_PROFIT_PIPS, self.symbol)

        if signal == "BUY":
            sl = price - sl_distance
            tp = price + tp_distance
        else:
            sl = price + sl_distance
            tp = price - tp_distance

        # สร้าง Request สำหรับส่ง Order
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.DEVIATION,
            "magic": self.magic_number,
            "comment": f"GoldBot {signal}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # ส่ง Order
        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code = result.retcode if result else "None"
            self.logger.error(f"❌ เปิด Order ไม่สำเร็จ - retcode: {error_code}")
            return False

        # บันทึกสถิติ
        self.trades_today += 1
        self.last_trade_date = datetime.now(tz=timezone.utc).date()

        # แสดงข้อความสัญญาณ
        reason_text = " | ".join(analysis.get("reasons", []))
        message = format_signal_message(signal, self.symbol, price, sl, tp, reason_text)
        self.logger.info(f"\n{message}")

        return True

    def close_all_positions(self) -> None:
        """ปิด Position ทั้งหมดที่เปิดอยู่"""
        if mt5 is None:
            return

        positions = self.get_open_positions()
        if not positions:
            self.logger.info("📋 ไม่มี Position ที่เปิดอยู่")
            return

        for position in positions:
            # กำหนดประเภท Order ปิด (ตรงข้ามกับที่เปิด)
            if position.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(self.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": position.ticket,
                "price": price,
                "deviation": config.DEVIATION,
                "magic": self.magic_number,
                "comment": "GoldBot Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ ปิด Position #{position.ticket} สำเร็จ")
            else:
                error_code = result.retcode if result else "None"
                self.logger.error(f"❌ ปิด Position #{position.ticket} ไม่สำเร็จ - retcode: {error_code}")

    def is_trading_time(self) -> bool:
        """
        ตรวจสอบว่าอยู่ในช่วงเวลาเทรดหรือไม่ (UTC)

        Returns:
            bool: True ถ้าอยู่ในช่วงเวลาเทรด
        """
        now = datetime.now(tz=timezone.utc)

        # ไม่เทรดในวันเสาร์-อาทิตย์ (weekday 5=เสาร์, 6=อาทิตย์)
        if now.weekday() >= 5:
            return False

        # ตรวจสอบช่วงเวลา
        return config.TRADING_START_HOUR <= now.hour < config.TRADING_END_HOUR

    def reset_daily_stats(self) -> None:
        """รีเซ็ตสถิติรายวันเมื่อขึ้นวันใหม่"""
        today = datetime.now(tz=timezone.utc).date()

        if self.last_trade_date is not None and self.last_trade_date != today:
            self.daily_loss = 0.0
            self.trades_today = 0
            self.logger.info(f"🔄 รีเซ็ตสถิติรายวัน - วันที่: {today}")

    def run(self) -> None:
        """Main Loop - รันบอทเทรด"""
        self.logger.info("=" * 60)
        self.logger.info("🤖 Gold Trading Bot เริ่มทำงาน")
        self.logger.info(f"   📌 Symbol    : {self.symbol}")
        self.logger.info(f"   ⏰ Timeframe : {self.timeframe}")
        self.logger.info(f"   🔮 Magic No. : {self.magic_number}")
        self.logger.info("=" * 60)

        # เชื่อมต่อ MT5
        if not self.connect_mt5():
            self.logger.error("❌ ไม่สามารถเชื่อมต่อ MT5 ได้ - หยุดการทำงาน")
            return

        start_time = datetime.now(tz=timezone.utc)
        total_signals = 0

        try:
            while True:
                try:
                    # รีเซ็ตสถิติรายวัน
                    self.reset_daily_stats()

                    # ตรวจสอบช่วงเวลาเทรด
                    if not self.is_trading_time():
                        now = datetime.now(tz=timezone.utc)
                        self.logger.debug(f"⏸️ นอกช่วงเวลาเทรด - {now.strftime('%H:%M')} UTC")
                        time.sleep(config.CHECK_INTERVAL_SECONDS)
                        continue

                    # ดึงข้อมูลตลาด
                    df = self.get_market_data()
                    if df is None:
                        self.logger.warning("⚠️ ไม่สามารถดึงข้อมูลตลาดได้")
                        time.sleep(config.CHECK_INTERVAL_SECONDS)
                        continue

                    # วิเคราะห์ตลาด
                    analysis = self.analyze_market(df)
                    signal = analysis["signal"]

                    # แสดงราคาปัจจุบัน
                    price_info = self.get_current_price()
                    if price_info:
                        self.logger.info(
                            f"💱 {self.symbol} | Bid: {price_info['bid']:.2f} | "
                            f"Ask: {price_info['ask']:.2f} | "
                            f"RSI: {analysis['rsi']:.1f} | "
                            f"Signal: {signal} (B:{analysis['buy_score']} S:{analysis['sell_score']})"
                        )

                    # เปิด Order ตามสัญญาณ
                    if signal in ("BUY", "SELL"):
                        total_signals += 1
                        self.open_trade(signal, analysis)

                    # แสดงสรุป Positions ที่เปิดอยู่
                    open_positions = self.get_open_positions()
                    if open_positions:
                        self.logger.info(f"📋 Open Positions: {len(open_positions)} รายการ")
                        for pos in open_positions:
                            self.logger.info(
                                f"   #{pos.ticket} | {'BUY' if pos.type == 0 else 'SELL'} | "
                                f"Lot: {pos.volume} | P&L: {pos.profit:.2f}"
                            )

                    time.sleep(config.CHECK_INTERVAL_SECONDS)

                except Exception as e:
                    self.logger.error(f"❌ เกิดข้อผิดพลาด: {e}", exc_info=True)
                    time.sleep(config.CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            # สรุปผลการทำงาน
            duration = datetime.now(tz=timezone.utc) - start_time
            self.logger.info("\n" + "=" * 60)
            self.logger.info("🛑 หยุดบอทด้วย KeyboardInterrupt")
            self.logger.info(f"   ⏱️ เวลาทำงาน   : {duration}")
            self.logger.info(f"   📊 สัญญาณทั้งหมด: {total_signals}")
            self.logger.info(f"   📈 เทรดวันนี้   : {self.trades_today}")
            self.logger.info(f"   💸 Loss วันนี้  : {self.daily_loss:.2f} USD")
            self.logger.info("=" * 60)

        finally:
            self.disconnect_mt5()


# ------------------------------------
# Entry Point
# ------------------------------------
if __name__ == "__main__":
    bot = GoldTradingBot()
    bot.run()
