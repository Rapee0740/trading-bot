# ============================================================
# config.py - ตั้งค่าพารามิเตอร์ทั้งหมดสำหรับ Gold Trading Bot
# ============================================================

# ------------------------------------
# MT5 Account Settings (ตั้งค่าบัญชี)
# แนะนำให้ใช้ Environment Variables แทนการ hardcode ในไฟล์นี้
# เช่น: MT5_LOGIN = int(os.environ.get("MT5_LOGIN", 0))
# ------------------------------------
MT5_LOGIN = 12345678
MT5_PASSWORD = "your_password"
MT5_SERVER = "your_broker_server"
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

# ------------------------------------
# Trading Symbol (สัญลักษณ์การเทรด)
# ------------------------------------
SYMBOL = "XAUUSD"

# ------------------------------------
# Timeframe (กรอบเวลา)
# ------------------------------------
TIMEFRAME = "H1"

# ------------------------------------
# EMA Settings (ค่า Exponential Moving Average)
# ------------------------------------
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21

# ------------------------------------
# RSI Settings (ค่า Relative Strength Index)
# ------------------------------------
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# ------------------------------------
# MACD Settings (Moving Average Convergence Divergence)
# ------------------------------------
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ------------------------------------
# Risk Management (การจัดการความเสี่ยง)
# ------------------------------------
LOT_SIZE = 0.01
MAX_POSITIONS = 3
STOP_LOSS_PIPS = 300
TAKE_PROFIT_PIPS = 600
MAX_DAILY_LOSS = 500.0
RISK_PERCENT = 1.0

# ------------------------------------
# Trading Schedule (ตารางเวลาเทรด UTC)
# ------------------------------------
TRADING_START_HOUR = 2
TRADING_END_HOUR = 21

# ------------------------------------
# Bot Settings (การตั้งค่าบอท)
# ------------------------------------
CHECK_INTERVAL_SECONDS = 60
MAGIC_NUMBER = 234000
DEVIATION = 20

# ------------------------------------
# Logging (การบันทึก Log)
# ------------------------------------
LOG_FILE = "trading_bot.log"
LOG_LEVEL = "INFO"
