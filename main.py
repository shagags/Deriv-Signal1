from fastapi import FastAPI, Query
import json, websocket, pandas as pd, datetime, os

APP_ID = os.getenv("DERIV_APP_ID", "1089")       # set in Render dashboard
app = FastAPI()


@app.get("/")                                    # friendly root
def root():
    return {"status": "Deriv Signal API • try /signal?symbol=R_25"}


def compute_signal(candles: list[dict]) -> dict:
    closes = [c["close"] for c in candles]
    lows   = [c["low"]   for c in candles]
    highs  = [c["high"]  for c in candles]

    s   = pd.Series(closes)
    mid = s.rolling(20).mean().iloc[-1]
    std = s.rolling(20).std().iloc[-1]
    upper, lower = mid + 2 * std, mid - 2 * std
    prev, last   = closes[-2], closes[-1]

    signal = "NO SIGNAL"
    if last > upper and prev > upper:
        signal = "SELL"
    elif last < lower and prev < lower:
        signal = "BUY"

    # --- take-profit (mid-band) & stop-loss (band extreme ±1 σ) ---
    if signal == "BUY":
        tp = round(mid, 3)
        sl = round(min(min(lows[-2:]), lower) - std, 3)
    elif signal == "SELL":
        tp = round(mid, 3)
        sl = round(max(max(highs[-2:]), upper) + std, 3)
    else:
        tp = sl = None

    return {
        "signal": signal,
        "entry":  round(last, 3),
        "tp":     tp,
        "sl":     sl,
        "utc":    datetime.datetime.utcnow().isoformat(" ", "seconds"),
    }


def get_signal(symbol: str) -> dict:
    ws = websocket.create_connection(
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    )
    ws.send(json.dumps({
        "ticks_history": symbol,
        "granularity":   60,
        "count":         40,
        "style":         "candles",
        "end":           "latest"
    }))
    resp = json.loads(ws.recv())
    ws.close()

    candles = resp["candles"] if "candles" in resp else resp["history"]["candles"]
    return compute_signal(candles)


@app.get("/signal")
def signal(symbol: str = Query("R_25", pattern="^R_(25|100)$")):
    """
    Examples:
      /signal?symbol=R_25
      /signal?symbol=R_100
    """
    return get_signal(symbol)
