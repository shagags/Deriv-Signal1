from fastapi import FastAPI, Query
import json, websocket, pandas as pd, datetime, os

APP_ID = os.getenv("DERIV_APP_ID", "1089")            # override in Render
app = FastAPI()


@app.get("/")
def root():
    return {"status": "Deriv Signal API — try /signal?symbol=R_25, R_100, or JD25"}


# ───────── helper to turn 40 candles into a trade idea ─────────
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

    # take-profit = mid-band | stop-loss = band extreme ±1 σ
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


# ───────── fetch 40 one-minute candles from Deriv WS ─────────
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

    candles = resp.get("candles") or resp["history"]["candles"]
    return compute_signal(candles)


# ───────── REST endpoint ─────────
@app.get("/signal")
def signal(
    symbol: str = Query(
        "R_25",
        description="R_25 (Vol 25) | R_100 (Vol 100) | JD25 (Jump 25)",
        regex="^(R_(25|100)|JD25)$"
    )
):
    """
    Examples:
      /signal?symbol=R_25   → Volatility 25
      /signal?symbol=R_100  → Volatility 100
      /signal?symbol=JD25  → Jump 25
    """
    return get_signal(symbol)
