import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="마켓 대시보드", page_icon="📈", layout="wide")

# 자동 새로고침 (60초)
REFRESH_SEC = 60
st.markdown(
    f'<meta http-equiv="refresh" content="{REFRESH_SEC}">',
    unsafe_allow_html=True,
)

TICKERS = {
    "주요 지수": {
        "코스피": "^KS11",
        "코스닥": "^KQ11",
        "니케이225": "^N225",
        "상해종합": "000001.SS",
        "대만 가권": "^TWII",
    },
    "선물": {
        "나스닥 선물": "NQ=F",
        "WTI 원유": "CL=F",
    },
    "환율": {
        "원/달러": "KRW=X",
        "달러 인덱스": "DX-Y.NYB",
    },
}


@st.cache_data(ttl=30)
def fetch_quote(symbol: str):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d", interval="1d")
        if hist.empty or len(hist) < 1:
            return None
        last = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last
        change = last - prev
        pct = (change / prev * 100) if prev else 0.0
        return {"price": last, "change": change, "pct": pct}
    except Exception as e:
        return {"error": str(e)}


def format_price(symbol: str, price: float) -> str:
    if symbol in ("KRW=X",):
        return f"{price:,.2f}"
    if symbol in ("DX-Y.NYB", "CL=F"):
        return f"{price:,.2f}"
    return f"{price:,.2f}"


st.title("📈 마켓 대시보드")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · {REFRESH_SEC}초마다 자동 새로고침")

for group, items in TICKERS.items():
    st.subheader(group)
    cols = st.columns(len(items))
    for col, (name, symbol) in zip(cols, items.items()):
        q = fetch_quote(symbol)
        with col:
            if not q or "error" in (q or {}):
                st.metric(name, "—", "데이터 없음")
            else:
                st.metric(
                    name,
                    format_price(symbol, q["price"]),
                    f"{q['change']:+,.2f} ({q['pct']:+.2f}%)",
                )

st.divider()
st.caption("데이터: Yahoo Finance · 지연 시세일 수 있음")
