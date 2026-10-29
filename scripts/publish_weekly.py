#!/usr/bin/env python3
"""Weekly Hebrew market report. Fails closed when any required market data is missing."""
import datetime as dt
import html
import json
import os
import pathlib
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WeeklyMarketReview/1.0)", "Accept": "application/json"}
SERIES = {
    "S&P 500": ["^GSPC"],
    "Nasdaq Composite": ["^IXIC"],
    "Dow Jones": ["^DJI"],
    "ת״א 35": ["^TA35", "TA35.TA"],
    "ת״א 90": ["^TA90", "TA90.TA"],
}
def prices(ticker):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(ticker, safe="") + "?range=2y&interval=1d"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as res:
        data = json.load(res)
    item = data["chart"]["result"][0]
    timestamps = item["timestamp"]
    closes = item["indicators"]["quote"][0]["close"]
    vals = sorted((dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), float(v)) for t, v in zip(timestamps, closes) if v is not None and v > 0)
    if len(vals) < 60:
        raise ValueError("Insufficient history for " + ticker)
    return vals
def at_or_before(series, date):
    values = [(day, price) for day, price in series if day <= date]
    if not values: raise ValueError("Missing reference closing price")
    return values[-1]
def pct(current, base):
    return 100 * (current / base - 1)
def fmt(n):
    return ("+" if n > 0 else "") + f"{n:.2f}%"
def escape(t):
    return html.escape(str(t))
def main():
    now = dt.datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    # The week just completed ends on the previous Friday.
    last_friday = now - dt.timedelta(days=(now.weekday() - 4) % 7)
    # On Sundays, last Friday is 2 days ago.
    week_start = last_friday - dt.timedelta(days=4)
    previous_friday = last_friday - dt.timedelta(days=7)
    year_end = dt.date(last_friday.year - 1, 12, 31)
    report_date = last_friday + dt.timedelta(days=2)
    if now != report_date and os.environ.get("ALLOW_NON_SUNDAY") != "1":
        raise SystemExit("Run on Sunday (Asia/Jerusalem) only.")
    info = []
    for label, tickers in SERIES.items():
        error = None
        series = None
        for ticker in tickers:
            try:
                series = prices(ticker)
                break
            except Exception as exc: error = exc
        if series is None: raise RuntimeError("No verified data for " + label + ": " + str(error))
        day, current = at_or_before(series, last_friday)
        if day < last_friday - dt.timedelta(days=3):
            raise RuntimeError("Stale market price for " + label + " at " + str(day))
        _, prev = at_or_before(series, previous_friday)
        _, ytd = at_or_before(series, year_end)
        info.append((label, fmt(pct(current, prev)), fmt(pct(current, ytd)), day.isoformat()))
    path = ROOT / "weekly" / report_date.isoformat() / "index.html"
    if path.exists():
        print("Existing report preserved: " + str(path))
        return
    table_rows = "".join("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in row) + "</tr>" for row in info)
    body = f'''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>סקירת שווקים שבועית {report_date:%d.%m.%Y}</title><style>
body{{margin:0;background:#f3f6f9;color:#172e42;font:16px/1.7 system-ui,Arial,sans-serif}}main{{max-width:800px;margin:auto;padding:24px 15px}}header{{background:#153b5d;color:#fff;padding:27px;border-radius:14px}}h1{{margin:0;font-size:29px}}h2{{color:#173c5b;font-size:20px}}section{{background:white;border:1px solid #dce5ec;border-radius:12px;padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse;min-width:400px}}th,td{{text-align:right;padding:12px 9px;border-bottom:1px solid #dde6ed}}th{{background:#eaf1f6}}.scroll{{overflow:auto}}.note{{color:#5e6f7e;font-size:13px}}a{{color:#236e9b}}</style></head><body><main><a href="../../">חזרה לארכיון</a><header><h1>סקירת שווקים שבועית</h1><p>שבוע המסחר {week_start:%d.%m.%Y}–{last_friday:%d.%m.%Y} | פורסם {report_date:%d.%m.%Y}</p></header><section><h2>ביצועי השווקים</h2><div class="scroll"><table><thead><tr><th>מדד</th><th>שבוע</th><th>מתחילת השנה</th><th>תאריך סגירה</th></tr></thead><tbody>{table_rows}</tbody></table></div><p class="note">תשואות מחיר במטבע המקומי, ללא דיבידנדים, ללא השפעת מטבע או עמלות. מקור: נתוני המחיר ההיסטוריים של Yahoo Finance. הנתונים נשלפו בעת ההפקה.</p></section><section><h2>ישראל ו־וול סטריט: השבוע שהיה</h2><p>סקירה מספרית של ביצועי המדדים מופיעה למעלה. לא נוסף ניתוח סיבתי או תיאור של אירועים ללא אימות עצמאי.</p></section><section><h2>השבוע הקרוב</h2><p>לוח אירועים ודוחות לא פורסם אוטומטית: נדרש אימות תאריכים ושעות ממקורות רשמיים. אין להציג מועדים משוערים כמאומתים.</p></section><p class="note">מאת דורון שרייבמן · לשימוש פנימי ליועצי השקעות · מידע כללי, אינו מהווה ייעוץ או שיווק השקעות.</p></main></body></html>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print("Published: " + str(path))
if __name__ == "__main__":
    main()
