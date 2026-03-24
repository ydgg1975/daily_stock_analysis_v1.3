import os
import requests

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"


def _request(params: dict) -> dict:
    if not API_KEY:
        raise ValueError("ALPHA_VANTAGE_API_KEY 未配置")

    params = {**params, "apikey": API_KEY}
    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if "Error Message" in data:
        raise ValueError(data["Error Message"])
    if "Note" in data:
        raise ValueError(data["Note"])

    return data


def get_rsi(symbol: str, interval: str = "daily", time_period: int = 14):
    data = _request({
        "function": "RSI",
        "symbol": symbol,
        "interval": interval,
        "time_period": time_period,
        "series_type": "close",
    })

    values = data.get("Technical Analysis: RSI", {})
    if not values:
        return None

    latest_key = sorted(values.keys(), reverse=True)[0]
    return float(values[latest_key]["RSI"])


def get_sma(symbol: str, period: int = 20, interval: str = "daily"):
    data = _request({
        "function": "SMA",
        "symbol": symbol,
        "interval": interval,
        "time_period": period,
        "series_type": "close",
    })

    values = data.get("Technical Analysis: SMA", {})
    if not values:
        return None

    latest_key = sorted(values.keys(), reverse=True)[0]
    return float(values[latest_key]["SMA"])