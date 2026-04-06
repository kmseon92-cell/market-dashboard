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
    "선물 · 환율": {
        "나스닥 선물": "NQ=F",
        "WTI 원유": "CL=F",
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
        <div style="padding:8px 14px;border:1px solid #2a2a2a;border-radius:10px;">
          <div style="font-size:1.05rem;font-weight:700;color:#000;margin-bottom:2px;">{name}</div>
          <div style="font-size:1.9rem;font-weight:800;line-height:1.1;color:{color};">
            {arrow} {pct:+.2f}%
          </div>
          <div style="font-size:0.8rem;color:{color};margin-top:0px;">
            {change:+,.2f}
          </div>
          <div style="font-size:1.15rem;font-weight:600;color:#000;margin-top:2px;">
            {format_price(symbol, q["price"])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


for group, items in TICKERS.items():
    st.markdown(f"<h5 style='margin:10px 0 6px 0;color:#000;'>{group}</h5>", unsafe_allow_html=True)
    cols = st.columns(len(items))
    for col, (name, symbol) in zip(cols, items.items()):
        with col:
            render_card(name, symbol, fetch_quote(symbol))

st.divider()

# 일일 리포트 (3단)
st.subheader("📰 일일 리포트")
import os
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
REPORT_FILES = [
    ("🇰🇷 국내증시 마감시황", "kr_market_close.md"),
    ("🐳 범고래 패턴 스크리닝", "bumgorae.md"),
    ("🇺🇸 미국증시 마감시황", "us_market_close.md"),
]

def load_report(fname: str) -> str:
    p = os.path.join(REPORTS_DIR, fname)
    if not os.path.exists(p):
        return "_아직 업데이트 안 됨_"
    with open(p, encoding="utf-8") as f:
        return f.read()

report_cols = st.columns(3)
for col, (title, fname) in zip(report_cols, REPORT_FILES):
    with col:
        st.markdown(f"#### {title}")
        content = load_report(fname)
        # 텔레그램 HTML(<b>) 그대로 렌더, 줄바꿈은 <br>로 변환
        rendered = content.replace("\n", "<br>")
        st.markdown(
            f'<div style="border:1px solid #2a2a2a;border-radius:10px;padding:14px;'
            f'height:600px;overflow-y:auto;font-size:0.88rem;line-height:1.6;color:#000;">'
            f'{rendered}</div>',
            unsafe_allow_html=True,
        )

st.divider()
st.caption("데이터: Yahoo Finance · 지연 시세일 수 있음")
