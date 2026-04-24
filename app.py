import re

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

REFRESH_SEC = 60

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


def _fetch_yf(symbol: str):
    info = yf.Ticker(symbol).info
    last = float(info.get("regularMarketPrice"))
    prev = float(info.get("regularMarketPreviousClose"))
    change = last - prev
    pct = (change / prev * 100) if prev else 0.0
    return {"price": last, "change": change, "pct": pct}


# yfinance .info가 전일종가=현재가로 고정 반환하는 종목은 stooq 우선
STOOQ_FIRST = {"CL=F"}


@st.cache_data(ttl=30)
def fetch_quote(symbol: str):
    try:
        if symbol in NAVER_INDEX_MAP:
            return _fetch_naver_kr(NAVER_INDEX_MAP[symbol])
        if symbol in STOOQ_FIRST and symbol in STOOQ_MAP:
            try:
                return _fetch_stooq(STOOQ_MAP[symbol])
            except Exception:
                return _fetch_yf(symbol)
        # 우선 yfinance, 실패/이상 시 stooq fallback
        try:
            return _fetch_yf(symbol)
        except Exception:
            if symbol in STOOQ_MAP:
                return _fetch_stooq(STOOQ_MAP[symbol])
            raise
    except Exception as e:
        return {"error": str(e)}


def format_price(symbol: str, price: float) -> str:
    if symbol in ("KRW=X",):
        return f"{price:,.2f}"
    if symbol in ("DX-Y.NYB", "CL=F"):
        return f"{price:,.2f}"
    return f"{price:,.2f}"


st.title("🐳 범고래 프로젝트")

@st.cache_data(ttl=3600)
def fetch_yf_ytd(symbols: tuple) -> dict:
    """yfinance 심볼 리스트 → {symbol: [(o,h,l,c), ...]} (YTD 일봉 OHLC, 배치)"""
    if not symbols:
        return {}
    from datetime import date
    start = f"{date.today().year}-01-01"
    result: dict[str, list[tuple[float, float, float, float]]] = {}
    try:
        df = yf.download(
            list(symbols), start=start, progress=False,
            auto_adjust=True, threads=True, group_by="ticker",
        )
    except Exception:
        return result
    if df is None or df.empty:
        return result
    for s in symbols:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if s not in df.columns.get_level_values(0):
                    continue
                sub = df[s][["Open", "High", "Low", "Close"]].dropna()
            else:
                sub = df[["Open", "High", "Low", "Close"]].dropna()
            if len(sub) >= 5:
                result[s] = [
                    (float(o), float(h), float(l), float(c))
                    for o, h, l, c in sub.itertuples(index=False, name=None)
                ]
        except Exception:
            continue
    return result


def make_mini_candlestick(ohlc: list[tuple[float, float, float, float]]) -> str:
    """카드용 소형 YTD 캔들차트 (차트만 반환, YTD% 라벨 없음)"""
    if not ohlc or len(ohlc) < 2:
        return ""
    w, h, pad = 140, 56, 2
    lows = [x[2] for x in ohlc]
    highs = [x[1] for x in ohlc]
    lo, hi = min(lows), max(highs)
    rng = (hi - lo) or 1.0
    n = len(ohlc)
    slot = (w - 2 * pad) / n
    body_w = max(1.0, slot * 0.7)

    def y(v: float) -> float:
        return h - pad - (h - 2 * pad) * (v - lo) / rng

    parts = []
    for i, (o, hv, lv, c) in enumerate(ohlc):
        cx = pad + slot * (i + 0.5)
        up = c >= o
        color = "#ef4444" if up else "#3b82f6"
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y(hv):.1f}" x2="{cx:.1f}" y2="{y(lv):.1f}" '
            f'stroke="{color}" stroke-width="0.6"/>'
        )
        top = y(max(o, c))
        bot = y(min(o, c))
        bh = max(0.8, bot - top)
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{top:.1f}" '
            f'width="{body_w:.1f}" height="{bh:.1f}" fill="{color}"/>'
        )
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'style="display:block;">{"".join(parts)}</svg>'
    )


def render_card(name: str, symbol: str, q: dict | None, ytd: list | None = None):
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

    chart_html = ""
    if ytd:
        first_close = ytd[0][3]
        last_close = ytd[-1][3]
        ytd_pct = (last_close / first_close - 1) * 100
        ytd_color = "#ef4444" if ytd_pct >= 0 else "#3b82f6"
        chart_html = (
            f'<div style="flex-shrink:0;text-align:right;">'
            f'{make_mini_candlestick(ytd)}'
            f'<div style="font-size:0.75rem;color:{ytd_color};font-weight:600;'
            f'margin-top:2px;">YTD {ytd_pct:+.1f}%</div>'
            f'</div>'
        )

    st.markdown(
        f"""
        <div style="padding:8px 14px;border:1px solid #2a2a2a;border-radius:10px;
                    display:flex;align-items:center;gap:10px;">
          <div style="flex:1;min-width:0;">
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
          {chart_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=f"{REFRESH_SEC}s")
def render_quotes():
    all_symbols = tuple(sym for items in TICKERS.values() for sym in items.values())
    ytd_map = fetch_yf_ytd(all_symbols)
    for group, items in TICKERS.items():
        st.markdown(f"<h5 style='margin:10px 0 6px 0;color:#000;'>{group}</h5>", unsafe_allow_html=True)
        cols = st.columns(len(items))
        for col, (name, symbol) in zip(cols, items.items()):
            with col:
                render_card(name, symbol, fetch_quote(symbol), ytd_map.get(symbol))
    st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} · {REFRESH_SEC}초마다 자동 갱신")

render_quotes()

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

import os
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


# 📅 실적 캘린더 — ETF 리더스 위, 영업일 5일치 가로 분할
def render_earnings_md(filename: str) -> None:
    p = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(p):
        st.caption("_아직 업데이트 안 됨_")
        return
    with open(p, encoding="utf-8") as f:
        text = f.read()

    body = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)
    body = re.sub(r"^📅[^\n]*\n", "", body)
    m = re.search(r"^기준:[^\n]*", body, flags=re.MULTILINE)
    as_of = m.group(0) if m else ""
    body = re.sub(r"^기준:[^\n]*\n", "", body)
    body = re.sub(r"^━+\n", "", body)

    if as_of:
        st.caption(as_of)

    block_re = re.compile(
        r"<b>(\d{2}/\d{2}\s*\([월화수목금토일]\)\s*·\s*\d+종목)</b>\n(.*?)(?=\n<b>\d{2}/\d{2}|\Z)",
        re.DOTALL,
    )
    blocks = [(mm.group(1), mm.group(2).strip()) for mm in block_re.finditer(body)]
    if not blocks:
        st.caption("_데이터 파싱 실패_")
        return

    cols = st.columns(len(blocks))
    for col, (header, content) in zip(cols, blocks):
        with col:
            st.markdown(f"#### {header}")
            rendered = content.replace("\n", "<br>")
            st.markdown(
                f'<div style="border:1px solid #2a2a2a;border-radius:10px;padding:12px;'
                f'font-size:0.88rem;line-height:1.55;color:#000;'
                f'max-height:480px;overflow-y:auto;">'
                f'{rendered}</div>',
                unsafe_allow_html=True,
            )


st.subheader("📅 한국 실적 캘린더")
render_earnings_md("kr_earnings_calendar.md")
st.divider()

st.subheader("📅 미국 실적 캘린더")
render_earnings_md("earnings_calendar.md")
st.divider()

# 🌍 ETF 리더스 — 미국증시 마감시황 아래, 전체 너비, 섹션 가로 분할
st.subheader("🌍 ETF 리더스 — 주도 국가·섹터")


def render_etf_leaders() -> None:
    p = os.path.join(REPORTS_DIR, "etf_leaders.md")
    if not os.path.exists(p):
        st.caption("_아직 업데이트 안 됨_")
        return
    with open(p, encoding="utf-8") as f:
        text = f.read()

    body = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)
    body = re.sub(r"^🌍[^\n]*\n", "", body)
    m = re.search(r"📅[^\n]*", body)
    as_of = m.group(0) if m else ""
    body = re.sub(r"^📅[^\n]*\n", "", body)
    body = re.sub(r"^━+\n", "", body)

    lines = body.split("\n")
    summary_lines: list[str] = []
    i = 0
    while i < len(lines) and lines[i].strip():
        summary_lines.append(lines[i])
        i += 1
    rest = "\n".join(lines[i:]).lstrip("\n")

    if as_of:
        st.caption(as_of)
    if summary_lines:
        st.markdown(
            f'<div style="padding:10px 14px;border:1px solid #2a2a2a;border-radius:10px;'
            f'font-size:1.0rem;color:#000;line-height:1.8;margin-bottom:14px;">'
            + "<br>".join(summary_lines)
            + "</div>",
            unsafe_allow_html=True,
        )

    section_re = re.compile(
        r"<b>(🌐[^<]+|🇺🇸[^<]+|🇰🇷[^<]+)</b>\n(.*?)(?=\n<b>(?:🌐|🇺🇸|🇰🇷)|\Z)",
        re.DOTALL,
    )
    sections = [(mm.group(1).strip(), mm.group(2).strip()) for mm in section_re.finditer(rest)]
    if not sections:
        return

    cols = st.columns(len(sections))
    for col, (title, content) in zip(cols, sections):
        with col:
            st.markdown(f"#### {title}")
            rendered = content.replace("\n", "<br>")
            st.markdown(
                f'<div style="border:1px solid #2a2a2a;border-radius:10px;padding:14px;'
                f'font-size:0.95rem;line-height:1.7;color:#000;">'
                f'{rendered}</div>',
                unsafe_allow_html=True,
            )


render_etf_leaders()
st.divider()

# 일일 리포트 (3단)
st.subheader("📰 일일 리포트")
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


KR_LINE_RE = re.compile(r'<b>([^<]+)</b>\s*\((\d{6})\)')
US_LINE_RE = re.compile(r'<b>([A-Z]{1,5})</b>\s+[A-Z]')
US_FULL_LINE_RE = re.compile(r'(<b>([A-Z]{1,5})</b>\s+[A-Z][^\n]*)')


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


@st.cache_data(ttl=300)
def fetch_kr_today_ohlc(codes: tuple) -> dict:
    """오늘 한국 종목 OHLC (네이버 차트 API) - yfinance 당일 미반영 보강용"""
    if not codes:
        return {}
    from datetime import date
    from concurrent.futures import ThreadPoolExecutor
    import urllib.request
    import json as _json

    today = date.today().strftime("%Y%m%d")
    start_dt, end_dt = f"{today}0000", f"{today}2359"

    def _fetch(code: str):
        url = (
            f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
            f"?startDateTime={start_dt}&endDateTime={end_dt}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=3).read()
            data = _json.loads(raw)
            if not data:
                return code, None
            row = data[-1]
            if str(row.get("localDate")) != today:
                return code, None
            return code, (
                float(row["openPrice"]),
                float(row["highPrice"]),
                float(row["lowPrice"]),
                float(row["closePrice"]),
            )
        except Exception:
            return code, None

    out: dict[str, tuple[float, float, float, float]] = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for code, ohlc in ex.map(_fetch, codes):
            if ohlc:
                out[code] = ohlc
    return out


@st.cache_data(ttl=600)
def fetch_kr_ytd(codes: tuple) -> dict:
    """한국 종목코드 리스트 → {code: [(o,h,l,c), ...]} (yfinance YTD + 네이버 당일 보강)"""
    if not codes:
        return {}
    from datetime import date
    start = f"{date.today().year}-01-01"
    today_str = date.today().strftime("%Y%m%d")
    result: dict[str, list[tuple[float, float, float, float]]] = {}
    last_date: dict[str, str] = {}

    def _batch(suffix: str, targets: list[str]) -> None:
        if not targets:
            return
        symbols = [f"{c}.{suffix}" for c in targets]
        try:
            df = yf.download(
                symbols, start=start, progress=False,
                auto_adjust=True, threads=True, group_by="ticker",
            )
        except Exception:
            return
        if df is None or df.empty:
            return
        for c in targets:
            sym = f"{c}.{suffix}"
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if sym not in df.columns.get_level_values(0):
                        continue
                    sub = df[sym][["Open", "High", "Low", "Close"]].dropna()
                else:
                    sub = df[["Open", "High", "Low", "Close"]].dropna()
                if len(sub) >= 5:
                    result[c] = [
                        (float(o), float(h), float(l), float(cl))
                        for o, h, l, cl in sub.itertuples(index=False, name=None)
                    ]
                    last_date[c] = sub.index[-1].strftime("%Y%m%d")
            except Exception:
                continue

    _batch("KS", list(codes))
    _batch("KQ", [c for c in codes if c not in result])

    # yfinance 당일 미반영 종목은 네이버 API로 오늘 봉 append
    missing = tuple(c for c in result if last_date.get(c) != today_str)
    if missing:
        today_data = fetch_kr_today_ohlc(missing)
        for c, ohlc in today_data.items():
            result[c].append(ohlc)

    return result


def make_candlestick(ohlc: list[tuple[float, float, float, float]]) -> str:
    """OHLC 리스트 → 인라인 SVG 캔들차트 (한국식: 양봉=빨강/음봉=파랑)"""
    if not ohlc or len(ohlc) < 2:
        return ""
    w, h, pad = 280, 90, 3
    lows = [x[2] for x in ohlc]
    highs = [x[1] for x in ohlc]
    lo, hi = min(lows), max(highs)
    rng = (hi - lo) or 1.0
    n = len(ohlc)
    slot = (w - 2 * pad) / n
    body_w = max(1.2, slot * 0.7)

    def y(v: float) -> float:
        return h - pad - (h - 2 * pad) * (v - lo) / rng

    first_close = ohlc[0][3]
    last_close = ohlc[-1][3]
    ytd_pct = (last_close / first_close - 1) * 100
    ytd_color = "#ef4444" if ytd_pct >= 0 else "#3b82f6"

    parts = []
    for i, (o, hv, lv, c) in enumerate(ohlc):
        cx = pad + slot * (i + 0.5)
        up = c >= o
        color = "#ef4444" if up else "#3b82f6"
        # 심지
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y(hv):.1f}" x2="{cx:.1f}" y2="{y(lv):.1f}" '
            f'stroke="{color}" stroke-width="0.7"/>'
        )
        # 몸통
        top = y(max(o, c))
        bot = y(min(o, c))
        bh = max(1.0, bot - top)
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{top:.1f}" '
            f'width="{body_w:.1f}" height="{bh:.1f}" fill="{color}"/>'
        )
    svg = "".join(parts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'style="vertical-align:middle;">{svg}</svg>'
        f'<span style="font-size:0.75rem;color:{ytd_color};font-weight:600;'
        f'margin-left:3px;">YTD {ytd_pct:+.1f}%</span>'
    )


@st.cache_data(ttl=3600)
def fetch_us_ytd(tickers: tuple) -> dict:
    """미국 티커 리스트 → {ticker: [(o,h,l,c), ...]} (yfinance YTD 일봉 OHLC, 배치)"""
    if not tickers:
        return {}
    from datetime import date
    start = f"{date.today().year}-01-01"
    result: dict[str, list[tuple[float, float, float, float]]] = {}
    try:
        df = yf.download(
            list(tickers), start=start, progress=False,
            auto_adjust=True, threads=True, group_by="ticker",
        )
    except Exception:
        return result
    if df is None or df.empty:
        return result
    for t in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if t not in df.columns.get_level_values(0):
                    continue
                sub = df[t][["Open", "High", "Low", "Close"]].dropna()
            else:
                sub = df[["Open", "High", "Low", "Close"]].dropna()
            if len(sub) >= 5:
                result[t] = [
                    (float(o), float(h), float(l), float(c))
                    for o, h, l, c in sub.itertuples(index=False, name=None)
                ]
        except Exception:
            continue
    return result


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


KR_SIDEWAYS_BLOCK_RE = re.compile(
    r'<b>[^<]+</b>\s*\((\d{6})\)(.*?)(?=<b>[^<]+</b>\s*\(\d{6}\)|\Z)',
    re.DOTALL,
)
KR_SIDEWAYS_DAYS_RE = re.compile(r'횡보[:：]\s*(\d+)\s*일')


def parse_kr_sideways(content: str) -> dict[str, int]:
    """범고래 리포트의 '횡보: N일' 파싱 → {code: days}"""
    out: dict[str, int] = {}
    for m in KR_SIDEWAYS_BLOCK_RE.finditer(content):
        code, block = m.group(1), m.group(2)
        dm = KR_SIDEWAYS_DAYS_RE.search(block)
        if dm:
            out[code] = int(dm.group(1))
    return out


def annotate_kr(content: str) -> str:
    """한국 종목: 종목명 | 실시간수익률 | 횡보일수 | YTD 캔들차트 + 신규 형광펜"""
    pairs = list(set(KR_LINE_RE.findall(content)))
    if not pairs:
        return content
    codes = tuple({code for _, code in pairs})
    code_to_pct = fetch_kr_pcts(codes)
    code_to_ytd = fetch_kr_ytd(codes)
    code_to_sideways = parse_kr_sideways(content)

    def repl(m):
        name, code = m.group(1), m.group(2)
        out = m.group(0)
        if code in code_to_pct:
            pct = code_to_pct[code]
            color = "#ef4444" if pct > 0 else ("#3b82f6" if pct < 0 else "#888")
            out += f' <span style="color:{color};font-weight:700;">실시간 {pct:+.2f}%</span>'
        if code in code_to_sideways:
            out += (
                f' <span style="color:#555;font-weight:600;'
                f'background:#eef2ff;padding:1px 6px;border-radius:4px;'
                f'font-size:0.85rem;">횡보 {code_to_sideways[code]}일</span>'
            )
        if code in code_to_ytd:
            out += "<br>" + make_candlestick(code_to_ytd[code])
        return out

    content = KR_LINE_RE.sub(repl, content)
    # 종목코드 (000000) 제거
    content = re.sub(r'\s*\(\d{6}\)', '', content)
    # 🟡 신규 종목 → 노란 형광펜 배경
    content = re.sub(
        r'🟡\s*<b>',
        '<span style="background:#fff176;padding:1px 4px;border-radius:3px;">🆕</span> <b>',
        content
    )
    return content


def annotate_us(content: str) -> str:
    """미국 종목: 종목명 줄 | 실시간수익률 → 다음 줄에 YTD 캔들차트"""
    tickers = list({m.group(2) for m in US_FULL_LINE_RE.finditer(content)})
    if not tickers:
        return content
    pcts = fetch_us_pcts(tuple(tickers))
    ohlc = fetch_us_ytd(tuple(tickers))

    def repl(m):
        full_line, ticker = m.group(1), m.group(2)
        out = full_line
        if ticker in pcts:
            pct = pcts[ticker]
            color = "#ef4444" if pct > 0 else ("#3b82f6" if pct < 0 else "#888")
            out += f' <span style="color:{color};font-weight:700;">실시간 {pct:+.2f}%</span>'
        if ticker in ohlc:
            out += "<br>" + make_candlestick(ohlc[ticker])
        return out

    return US_FULL_LINE_RE.sub(repl, content)


report_cols = st.columns(3)
for col, (title, fname) in zip(report_cols, REPORT_FILES):
    with col:
        st.markdown(f"#### {title}")
        content = load_report(fname)
        if "kr_market_close" in fname:
            # 종목 간 한 줄 띄우기 (차트 때문에 조밀해 보여서)
            content = re.sub(
                r'\n(\s*<b>[^<]+</b>\s*\(\d{6}\))',
                r'\n\n\1',
                content,
            )
        if "kr_market_close" in fname or "bumgorae" in fname:
            content = annotate_kr(content)
        elif "us_market_close" in fname:
            # 종목 간 한 줄 띄우기
            content = re.sub(
                r'\n(\s*<b>[A-Z]{1,5}</b>\s+[A-Z])',
                r'\n\n\1',
                content,
            )
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
