import urllib.request
import urllib.parse
import json
import time
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

BASE = "https://fapi.binance.com"
TOKEN = "9061084679:AAFBWmomCneTRndwCcUfViukqYAXQZmArGE"
CHAT_ID = "1729860544"

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Binance Scanner is Running 24/7!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), KeepAliveHandler).serve_forever()

def get_json(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        print("Telegram message sent!")
    except Exception as e:
        print("TG Error:", e)

def ema(vals, p):
    k, res = 2 / (p + 1), [vals[0]]
    for v in vals[1:]:
        res.append(v * k + res[-1] * (1 - k))
    return res

def get_macd(sym, tf):
    data = get_json(f"{BASE}/fapi/v1/klines", {"symbol": sym, "interval": tf, "limit": 100})
    c = [float(x[4]) for x in data[:-1]]
    if len(c) < 35:
        return None, None
    m = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    return m, ema(m, 9)

def check(sym, is_long):
    m15, s15 = get_macd(sym, "15m")
    if not m15:
        return False
    ok15 = (m15[-1] > s15[-1] and m15[-1] > m15[-2]) if is_long else (m15[-1] < s15[-1] and m15[-1] < m15[-2])
    if not ok15:
        return False
    m3, s3 = get_macd(sym, "3m")
    if not m3:
        return False
    return (m3[-2] <= s3[-2] and m3[-1] > s3[-1]) if is_long else (m3[-2] >= s3[-2] and m3[-1] < s3[-1])

def run():
    try:
        t = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{t}] Scanning...")
        info = get_json(f"{BASE}/fapi/v1/exchangeInfo")
        valid = {x["symbol"] for x in info["symbols"] if x["quoteAsset"] == "USDT" and x["contractType"] == "PERPETUAL" and x["status"] == "TRADING"}
        tickers = get_json(f"{BASE}/fapi/v1/ticker/24hr")

        longs = [x["symbol"] for x in tickers if x["symbol"] in valid and float(x["priceChangePercent"]) >= 12]
        shorts = [x["symbol"] for x in tickers if x["symbol"] in valid and float(x["priceChangePercent"]) <= -12]
        print(f"Watchlist -> Longs (+12%): {len(longs)} | Shorts (-12%): {len(shorts)}")

        fl, fs = [], []
        for s in longs:
            try:
                if check(s, True): fl.append(s)
                time.sleep(0.2)
            except Exception: pass

        for s in shorts:
            try:
                if check(s, False): fs.append(s)
                time.sleep(0.2)
            except Exception: pass

        if fl or fs:
            msg = f"<b>BINANCE 3m CROSSOVER</b>\nTime: {t} UTC\n\n"
            if fl: msg += "<b>LONG (15m UP + 3m CROSS):</b>\n" + "".join(f"- #{s}\n" for s in fl) + "\n"
            if fs: msg += "<b>SHORT (15m DOWN + 3m CROSS):</b>\n" + "".join(f"- #{s}\n" for s in fs)
            print(msg.replace("<b>", "").replace("</b>", ""))
            send_tg(msg)
        else:
            print("No new crossover signal.")
    except Exception as e:
        print("ERROR:", e)

if _name_ == "_main_":
    threading.Thread(target=start_web_server, daemon=True).start()
    print("Scanner Started on Cloud Server!")
    send_tg("✅ <b>Binance Scanner Started!</b>\nServer is Live 24/7.")
    run()
    while True:
        w = 180 - (time.time() % 180) + 2
        time.sleep(w)
        run()
