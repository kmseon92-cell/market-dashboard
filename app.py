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


NAVER_INDEX_MAP = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ"}

# 야후 심볼 → stooq 심볼
STOOQ_MAP = {
    "^N225": "^nkx",
    "000001.SS": "^shc",
    "^TWII": "^twse",
    "NQ=F": "nq.f",
    "CL=F": "cl.f",
    "KRW=X": "usdkrw",
    "DX-Y.NYB": "dx.f",
}


def _fetch_naver_kr(code: str):
    import urllib.request, json
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:{code}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
    d = data["result"]["areas"][0]["datas"][0]
    last = d["nv"] / 100
    change = abs(d["cv"]) / 100
    pct = abs(float(d["cr"]))
    # rf: 1=상한 2=상승 3=보합 4=하한 5=하락
    if str(d.get("rf")) in ("4", "5"):
        change = -change
        pct = -pct
    return {"price": last, "change": change, "pct": pct}


def _fetch_stooq(sym: str):
    import urllib.request
    url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcvp&h&e=csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=5).read().decode().strip()
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("no data")
    row = lines[1].split(",")
    # Symbol,Date,Time,Open,High,Low,Close,Volume,Prev
    if row[1] == "N/D":
        raise ValueError("N/D")
    last = float(row[6])
    prev = float(row[8])
    change = last - prev
    pct = (change / prev * 100) if prev else 0.0
    return {"price": last, "change": change, "pct": pct}


@st.cache_data(ttl=30)
def fetch_quote(symbol: str):
    try:
        if symbol in NAVER_INDEX_MAP:
            return _fetch_naver_kr(NAVER_INDEX_MAP[symbol])
        if symbol in STOOQ_MAP:
            return _fetch_stooq(STOOQ_MAP[symbol])
        # fallback: yfinance
        t = yf.Ticker(symbol)
        info = t.info
        last = float(info.get("regularMarketPrice"))
        prev = float(info.get("regularMarketPreviousClose"))
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
def fetch_kr_pcts(codes: tuple) -> dict:
    """한국 종목코드 리스트 → {code: pct} (네이버 실시간)"""
    if not codes:
        return {}
    import urllib.request, json
    try:
        q = ",".join(codes)
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
        )
        raw = urllib.request.urlopen(req, timeout=5).read().decode("euc-kr", "ignore")
        data = json.loads(raw)
        out = {}
        for d in data["result"]["areas"][0]["datas"]:
            pct = abs(float(d.get("cr", 0)))
            if str(d.get("rf")) in ("4", "5"):
                pct = -pct
            out[d["cd"]] = pct
        return out
    except Exception:
        return {}


@st.cache_data(ttl=60)
def fetch_us_pcts(tickers: tuple) -> dict:
    """미국 티커 리스트 → {ticker: pct} (Stooq)"""
    if not tickers:
        return {}
    import urllib.request
    out = {}
    syms = ",".join(t.lower() + ".us" for t in tickers)
    url = f"https://stooq.com/q/l/?s={syms}&f=sd2t2ohlcvp&h&e=csv"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=5).read().decode().strip()
        lines = text.splitlines()[1:]
        for line in lines:
            row = line.split(",")
            if len(row) < 9 or row[1] == "N/D":
                continue
            try:
                last = float(row[6])
                prev = float(row[8])
                if prev:
                    sym = row[0].replace(".US", "").upper()
                    out[sym] = (last / prev - 1) * 100
            except ValueError:
                continue
    except Exception:
        pass
    return out


def annotate_kr(content: str) -> str:
    """한국 종목 라인에 당일 등락률 추가"""
    pairs = list(set(KR_LINE_RE.findall(content)))
    if not pairs:
        return content
    codes = tuple({code for _, code in pairs})
    code_to_pct = fetch_kr_pcts(codes)

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
    pcts = fetch_us_pcts(tuple(tickers))

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
