# ============================================================
# utils.py - ฟังก์ชันคำนวณ Technical Indicators และ Utility
# ============================================================

import pandas as pd
import numpy as np


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    คำนวณ Exponential Moving Average (EMA)

    Args:
        data: ข้อมูลราคา (Series)
        period: จำนวนช่วงเวลา

    Returns:
        pd.Series: ค่า EMA
    """
    return data.ewm(span=period, adjust=False).mean()


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    คำนวณ Relative Strength Index (RSI) ด้วย Wilder's smoothing method

    Args:
        data: ข้อมูลราคาปิด (Series)
        period: จำนวนช่วงเวลา (default: 14)

    Returns:
        pd.Series: ค่า RSI (0-100)
    """
    delta = data.diff()

    # แยกการเปลี่ยนแปลงบวกและลบ
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # ใช้ Wilder's smoothing (EMA แบบพิเศษ)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    # คำนวณ RS และ RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)  # ถ้าคำนวณไม่ได้ให้ใช้ 50 (กลางๆ)


def calculate_macd(
    data: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    คำนวณ MACD (Moving Average Convergence Divergence)

    Args:
        data: ข้อมูลราคาปิด (Series)
        fast: ช่วง EMA เร็ว (default: 12)
        slow: ช่วง EMA ช้า (default: 26)
        signal: ช่วง Signal Line (default: 9)

    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)

    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    คำนวณ Average True Range (ATR)

    Args:
        high: ราคาสูงสุด (Series)
        low: ราคาต่ำสุด (Series)
        close: ราคาปิด (Series)
        period: จำนวนช่วงเวลา (default: 14)

    Returns:
        pd.Series: ค่า ATR
    """
    prev_close = close.shift(1)

    # คำนวณ True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # คำนวณ ATR ด้วย EMA
    atr = true_range.ewm(alpha=1 / period, adjust=False).mean()

    return atr


def calculate_bollinger_bands(
    data: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    คำนวณ Bollinger Bands

    Args:
        data: ข้อมูลราคาปิด (Series)
        period: ช่วง Moving Average (default: 20)
        std_dev: จำนวน Standard Deviation (default: 2.0)

    Returns:
        tuple: (upper_band, middle_band, lower_band)
    """
    middle = data.rolling(window=period).mean()
    std = data.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return upper, middle, lower


def pip_to_price(pips: int, symbol: str = "XAUUSD") -> float:
    """
    แปลง Pips เป็นราคา

    Args:
        pips: จำนวน pips
        symbol: สัญลักษณ์การเทรด (default: "XAUUSD")

    Returns:
        float: มูลค่าในหน่วยราคา
    """
    # ทองคำ (XAUUSD) = 0.01 ต่อ point
    if "XAU" in symbol or "GOLD" in symbol.upper():
        return pips * 0.01

    # Forex คู่สกุลเงิน = 0.0001 ต่อ pip
    return pips * 0.0001


def calculate_position_size(
    balance: float,
    risk_percent: float,
    sl_pips: int,
    pip_value: float = 1.0,
) -> float:
    """
    คำนวณขนาด Lot ที่เหมาะสมตามความเสี่ยง

    Args:
        balance: ยอดเงินในบัญชี
        risk_percent: เปอร์เซ็นต์ความเสี่ยงต่อการเทรด
        sl_pips: ระยะ Stop Loss ในหน่วย pips
        pip_value: มูลค่าต่อ pip (default: 1.0)

    Returns:
        float: ขนาด Lot (ขั้นต่ำ 0.01)
    """
    # คำนวณจำนวนเงินที่ยอมเสียได้
    risk_amount = balance * (risk_percent / 100)

    # คำนวณ Lot Size
    if sl_pips > 0 and pip_value > 0:
        lot_size = risk_amount / (sl_pips * pip_value)
    else:
        lot_size = 0.01

    # ขนาด Lot ขั้นต่ำคือ 0.01
    return max(round(lot_size, 2), 0.01)


def format_signal_message(
    signal_type: str,
    symbol: str,
    price: float,
    sl: float,
    tp: float,
    reason: str,
) -> str:
    """
    สร้างข้อความสัญญาณการเทรดในรูปแบบที่อ่านง่าย

    Args:
        signal_type: ประเภทสัญญาณ ("BUY" หรือ "SELL")
        symbol: สัญลักษณ์การเทรด
        price: ราคาเข้า
        sl: ราคา Stop Loss
        tp: ราคา Take Profit
        reason: เหตุผลของสัญญาณ

    Returns:
        str: ข้อความสัญญาณที่จัดรูปแบบแล้ว
    """
    # เลือก emoji ตามประเภทสัญญาณ
    if signal_type == "BUY":
        emoji = "🟢"
        direction = "ซื้อ (BUY)"
    else:
        emoji = "🔴"
        direction = "ขาย (SELL)"

    message = (
        f"{emoji} สัญญาณ {direction}\n"
        f"   💱 Symbol : {symbol}\n"
        f"   💰 Price  : {price:.2f}\n"
        f"   🛑 SL     : {sl:.2f}\n"
        f"   🎯 TP     : {tp:.2f}\n"
        f"   📊 เหตุผล : {reason}"
    )

    return message
