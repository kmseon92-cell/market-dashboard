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

def render_card(name: str, symbol: str, q: dict | None):
    if not q or "error" in (q or {}):
        st.markdown(
            f"""
            <div style="padding:12px 14px;border:1px solid #2a2a2a;border-radius:10px;">
              <div style="font-size:0.9rem;color:#aaa;">{name}</div>
              <div style="font-size:1.8rem;font-weight:700;color:#888;">—</div>
              <div style="font-size:0.85rem;color:#888;">데이터 없음</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    pct = q["pct"]
    change = q["change"]
    color = "#ef4444" if pct > 0 else ("#3b82f6" if pct < 0 else "#9ca3af")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "■")
    st.markdown(
        f"""
        <div style="padding:14px 16px;border:1px solid #2a2a2a;border-radius:10px;">
          <div style="font-size:0.95rem;color:#aaa;margin-bottom:6px;">{name}</div>
          <div style="font-size:2.4rem;font-weight:800;line-height:1.1;color:{color};">
            {arrow} {pct:+.2f}%
          </div>
          <div style="font-size:0.85rem;color:{color};margin-top:2px;">
            {change:+,.2f}
          </div>
          <div style="font-size:1.0rem;color:#ddd;margin-top:6px;">
            {format_price(symbol, q["price"])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


for group, items in TICKERS.items():
    st.subheader(group)
    cols = st.columns(len(items))
    for col, (name, symbol) in zip(cols, items.items()):
        with col:
            render_card(name, symbol, fetch_quote(symbol))

st.divider()
st.caption("데이터: Yahoo Finance · 지연 시세일 수 있음")
