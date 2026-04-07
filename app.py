import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="범고래 프로젝트", page_icon="🐳", layout="wide")


def check_password():
    import hashlib
    secret = st.secrets.get("APP_PASSWORD", "")
    if not secret:
        return  # secret 미설정 시 통과
    token = hashlib.sha256(f"bumgorae:{secret}".encode()).hexdigest()[:24]

    # URL 쿼리 파라미터에 토큰 있으면 통과 (meta refresh에도 유지됨)
    if st.query_params.get("auth") == token:
        return

    def on_submit():
        if st.session_state.get("pw_input") == secret:
            st.query_params["auth"] = token
        else:
            st.session_state["pw_wrong"] = True

    st.markdown("### 🐳 범고래 프로젝트")
    st.text_input("비밀번호", type="password", on_change=on_submit, key="pw_input")
    if st.session_state.get("pw_wrong"):
        st.error("비밀번호가 틀렸어")
    st.stop()


check_password()

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
        fi = t.fast_info
        last = float(fi["last_price"])
        prev = float(fi["previous_close"])
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


st.title("🐳 범고래 프로젝트")
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

# 미국증시 마감시황 한 줄 (us_market_close.md에서 추출)
def extract_us_summary() -> str:
    import os
    p = os.path.join(os.path.dirname(__file__), "reports", "us_market_close.md")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        text = f.read()
    # ━━━ 다음 줄이 요약
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "━" in line and i + 1 < len(lines):
            return lines[i + 1].strip()
    return ""

us_summary = extract_us_summary()
if us_summary:
    import re as _re
    def _color_pct(m):
        val = m.group(0)
        color = "#ef4444" if val.startswith("+") else "#3b82f6"
        return f'<span style="color:{color};font-weight:700;">{val}</span>'
    colored_summary = _re.sub(r'[+\-]\d+\.\d+%', _color_pct, us_summary)
    st.markdown("<h5 style='margin:10px 0 6px 0;color:#000;'>🇺🇸 미국증시 마감시황</h5>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="padding:10px 14px;border:1px solid #2a2a2a;border-radius:10px;'
        f'font-size:1.0rem;color:#000;font-weight:500;">{colored_summary}</div>',
        unsafe_allow_html=True,
    )
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


import re

KR_LINE_RE = re.compile(r'<b>([^<]+)</b>\s*\((\d{6})\)')
US_LINE_RE = re.compile(r'<b>([A-Z]{1,5})</b>\s+[A-Z]')


@st.cache_data(ttl=60)
def fetch_intraday_pcts(symbols: tuple) -> dict:
    """심볼 리스트 → {symbol: pct} 당일 등락률"""
    if not symbols:
        return {}
    try:
        df = yf.download(list(symbols), period="5d", interval="1d",
                         progress=False, group_by="ticker", threads=True)
        result = {}
        for sym in symbols:
            try:
                if len(symbols) == 1:
                    closes = df["Close"]
                else:
                    closes = df[sym]["Close"]
                closes = closes.dropna()
                if len(closes) >= 2:
                    pct = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
                    result[sym] = float(pct)
                # 1개 이하면 데이터 부족 — 표시 안 함 (이전엔 0%로 잘못 표시)
            except Exception:
                continue
        return result
    except Exception:
        return {}


def annotate_kr(content: str) -> str:
    """한국 종목 라인에 당일 등락률 추가"""
    codes = list(set(KR_LINE_RE.findall(content)))
    if not codes:
        return content
    # .KS 먼저 시도
    ks_syms = tuple(f"{c[1]}.KS" for c in codes)
    ks_pcts = fetch_intraday_pcts(ks_syms)
    # 결측은 .KQ로 재시도
    missing = [c for c in codes if f"{c[1]}.KS" not in ks_pcts]
    kq_pcts = {}
    if missing:
        kq_syms = tuple(f"{c[1]}.KQ" for c in missing)
        kq_pcts = fetch_intraday_pcts(kq_syms)

    code_to_pct = {}
    for name, code in codes:
        if f"{code}.KS" in ks_pcts:
            code_to_pct[code] = ks_pcts[f"{code}.KS"]
        elif f"{code}.KQ" in kq_pcts:
            code_to_pct[code] = kq_pcts[f"{code}.KQ"]

    def repl(m):
        name, code = m.group(1), m.group(2)
        if code in code_to_pct:
            pct = code_to_pct[code]
            color = "#ef4444" if pct > 0 else ("#3b82f6" if pct < 0 else "#888")
            badge = f' <span style="color:{color};font-weight:700;">실시간 {pct:+.2f}%</span>'
            return m.group(0) + badge
        return m.group(0)

    content = KR_LINE_RE.sub(repl, content)
    # 종목코드 (000000) 제거
    content = re.sub(r'\s*\(\d{6}\)', '', content)
    return content


def annotate_us(content: str) -> str:
    """미국 종목 라인에 당일 등락률 추가"""
    tickers = list(set(US_LINE_RE.findall(content)))
    if not tickers:
        return content
    pcts = fetch_intraday_pcts(tuple(tickers))

    def repl(m):
        ticker = m.group(1)
        if ticker in pcts:
            pct = pcts[ticker]
            color = "#ef4444" if pct > 0 else ("#3b82f6" if pct < 0 else "#888")
            badge = f' <span style="color:{color};font-weight:700;">실시간 {pct:+.2f}%</span>'
            # ticker 매치 끝에 붙이지 말고 한 줄 끝에 붙여야 자연스러움 — 대신 ticker 뒤에 붙임
            return m.group(0)[:-1] + badge + m.group(0)[-1]
        return m.group(0)

    return US_LINE_RE.sub(repl, content)


report_cols = st.columns(3)
for col, (title, fname) in zip(report_cols, REPORT_FILES):
    with col:
        st.markdown(f"#### {title}")
        content = load_report(fname)
        if "kr_market_close" in fname or "bumgorae" in fname:
            content = annotate_kr(content)
        elif "us_market_close" in fname:
            content = annotate_us(content)
        # 텔레그램 HTML(<b>) 그대로 렌더, 줄바꿈은 <br>로 변환
        rendered = content.replace("\n", "<br>")
        st.markdown(
            f'<div style="border:1px solid #2a2a2a;border-radius:10px;padding:14px;'
            f'font-size:1.05rem;line-height:1.7;color:#000;">'
            f'{rendered}</div>',
            unsafe_allow_html=True,
        )

st.divider()
st.caption("데이터: Yahoo Finance · 지연 시세일 수 있음")
