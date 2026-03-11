# 🤖 Gold Trading Bot for MetaTrader 5

บอทเทรดทองคำ (XAUUSD) อัตโนมัติผ่าน MetaTrader 5 ด้วย Python พร้อมระบบ Backtesting

---

## ✨ คุณสมบัติหลัก

- 🔗 **เชื่อมต่อ MT5 อัตโนมัติ** - เชื่อมต่อกับ MetaTrader 5 terminal
- 📊 **วิเคราะห์ทางเทคนิค** - EMA Crossover + RSI + MACD Scoring System
- 🤖 **เปิด/ปิด Order อัตโนมัติ** - ส่ง Order โดยไม่ต้องควบคุมด้วยตนเอง
- 🛡️ **จัดการความเสี่ยง** - Stop Loss, Take Profit, Daily Loss Limit, Max Positions
- 📈 **ระบบ Backtest** - ทดสอบกลยุทธ์ย้อนหลังพร้อม Win Rate และสถิติครบ
- 📋 **Logging ละเอียด** - บันทึก log ทั้งไฟล์และ console
- 📅 **Export CSV** - Export ผลการเทรดเป็นไฟล์ CSV

---

## 📁 โครงสร้างไฟล์

```
trading-bot/
├── config.py           # ตั้งค่าพารามิเตอร์ทั้งหมด
├── utils.py            # ฟังก์ชัน Technical Indicators
├── gold_trading_bot.py # บอทเทรดหลัก
├── backtester.py       # ระบบ Backtesting
├── requirements.txt    # Python dependencies
└── README.md           # เอกสารนี้
```

---

## 🔧 การติดตั้ง

### 1. ติดตั้ง Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. ติดตั้ง MetaTrader 5 Terminal

- ดาวน์โหลด MetaTrader 5 จาก broker ของคุณ
- เปิด MT5 terminal และ login เข้าบัญชี
- เปิดใช้งาน **Algo Trading** (Tools → Options → Expert Advisors → Allow algorithmic trading)

---

## ⚙️ การตั้งค่า

แก้ไขไฟล์ `config.py`:

```python
# ข้อมูลบัญชี MT5
MT5_LOGIN = 12345678           # หมายเลขบัญชี
MT5_PASSWORD = "your_password" # รหัสผ่าน
MT5_SERVER = "your_broker"     # ชื่อ server ของ broker
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

# การเทรด
SYMBOL = "XAUUSD"    # สัญลักษณ์ทองคำ
TIMEFRAME = "H1"     # กรอบเวลา H1

# ความเสี่ยง
LOT_SIZE = 0.01       # ขนาด lot
STOP_LOSS_PIPS = 300  # Stop Loss (pips)
TAKE_PROFIT_PIPS = 600 # Take Profit (pips)
MAX_DAILY_LOSS = 500.0 # ขาดทุนสูงสุดต่อวัน (USD)
RISK_PERCENT = 1.0     # ความเสี่ยงต่อการเทรด (%)
```

---

## 🚀 วิธีใช้งาน

### เทรดจริง (Live Trading)

```bash
python gold_trading_bot.py
```

### Backtest

```bash
# Backtest ย้อนหลัง 365 วัน (default)
python backtester.py

# Backtest ย้อนหลัง 180 วัน
python backtester.py --days 180

# Backtest ช่วงวันที่กำหนด
python backtester.py --start 2025-01-01 --end 2026-03-01

# Backtest พร้อม export CSV
python backtester.py --days 365 --balance 5000 --export
```

#### ตัวเลือก Backtest

| ตัวเลือก | ค่าเริ่มต้น | คำอธิบาย |
|---------|-----------|---------|
| `--days` | 365 | จำนวนวันย้อนหลัง |
| `--start` | - | วันที่เริ่มต้น (YYYY-MM-DD) |
| `--end` | - | วันที่สิ้นสุด (YYYY-MM-DD) |
| `--balance` | 10000 | ยอดเงินเริ่มต้น (USD) |
| `--export` | false | Export ผลเป็นไฟล์ CSV |

---

## 📊 กลยุทธ์การเทรด

### EMA Crossover + RSI + MACD Scoring System

บอทใช้ระบบคะแนนรวม (Scoring) จาก 3 indicators:

| เงื่อนไข | คะแนน |
|--------|------|
| EMA Crossover (EMA9 ตัด EMA21) | +3 |
| EMA Trend Direction | +1 |
| RSI Oversold (<30) / Overbought (>70) | +2 |
| RSI ต่ำกว่า/สูงกว่า 50 | +1 |
| MACD Histogram Crossover | +2 |
| MACD Direction | +1 |

- **BUY Signal**: `buy_score >= 4` และ `buy_score > sell_score`
- **SELL Signal**: `sell_score >= 4` และ `sell_score > buy_score`

---

## 🛡️ การจัดการความเสี่ยง

- **Stop Loss**: กำหนดระยะ SL ใน pips (`STOP_LOSS_PIPS`)
- **Take Profit**: กำหนดระยะ TP ใน pips (`TAKE_PROFIT_PIPS`)
- **Max Positions**: จำกัดจำนวน positions ที่เปิดพร้อมกัน (`MAX_POSITIONS`)
- **Daily Loss Limit**: หยุดเทรดเมื่อขาดทุนถึงขีดจำกัดต่อวัน (`MAX_DAILY_LOSS`)
- **Risk-Based Position Size**: คำนวณขนาด lot ตาม % ความเสี่ยงต่อยอดเงิน

---

## ⚠️ คำเตือน (Disclaimer)

> **กรุณาอ่านและทำความเข้าใจก่อนใช้งาน**
>
> - ⚠️ **ทดสอบด้วย Demo Account ก่อนเสมอ** ก่อนนำไปใช้งานจริง
> - ⚠️ **ไม่รับประกันกำไร** - การเทรด Forex/Gold มีความเสี่ยงสูง อาจขาดทุนได้
> - ⚠️ **ผู้ใช้รับผิดชอบเอง** - Developer ไม่รับผิดชอบต่อผลขาดทุนใดๆ ที่เกิดจากการใช้บอทนี้
> - ⚠️ **ศึกษากลยุทธ์ให้เข้าใจ** ก่อน Deploy ใช้งานจริง
> - ⚠️ **ตลาด Forex/Gold มีความผันผวนสูง** ผลการ Backtest ไม่ได้การันตีผลในอนาคต
