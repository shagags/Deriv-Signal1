from fastapi import FastAPI, Query
import json, websocket, pandas as pd, datetime, os

APP_ID  = os.getenv("DERIV_APP_ID", "1089")  # set later in Render
app = FastAPI()

def root():
    return {"status": "Deriv Signal API. Try /signal?symbol=R_25"}

def get_signal(symbol: str):
    ws = websocket.create_connection(
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}")
    ws.send(json.dumps({
        "ticks_history": symbol,
        "granularity": 60,
        "count": 40,
        "style": "candles",
        "end": "latest"
    }))
    resp = json.loads(ws.recv()); ws.close()
    candles = (resp["candles"]
               if resp["msg_type"] == "candles"
               else resp["history"]["candles"])
    closes = [c["close"] for c in candles]
    s = pd.Series(closes)
    mid = s.rolling(20).mean().iloc[-1]
    std = s.rolling(20).std().iloc[-1]
    upper, lower = mid+2*std, mid-2*std
    prev, last  = closes[-2], closes[-1]
    signal = ("SELL" if last>upper and prev>upper
              else "BUY" if last<lower and prev<lower
              else "NO SIGNAL")
    return {"signal": signal,
            "last": last,
            "utc":  datetime.datetime.utcnow().isoformat(" ", "seconds")}

@app.get("/signal")
def signal(symbol: str = Query("R_25", pattern="^R_(25|100)$")):
    return get_signal(symbol)
