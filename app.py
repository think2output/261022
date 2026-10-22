"""공공기관 채용 알림 (Streamlit).

한국 시간 9시, 13시, 18시에 진행 중인 공고를 다시 확인하고,
페이지를 켜둔 사람에게 새로 올라온 공고를 토스트와 브라우저 알림으로 알려준다.
같은 공고를 목록, 지도, 넘겨보기로 볼 수 있고, 관심/패스 기록은 브라우저(localStorage)에 남는다.
조건(필터)은 URL 쿼리 파라미터에 저장되므로 북마크하면 그대로 다시 열린다.

실행: streamlit run app.py
"""
import html
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import widgets
from jobs import (EDUCATIONS, FILE_TYPES, HIRE_TYPES, NCS, RECRUIT_KINDS, REGIONS,
                  fetch_detail, fetch_ongoing)

KST = timezone(timedelta(hours=9))
CHECK_HOURS = (9, 13, 18)
PAGE_STEP = 30
PASSED_LIMIT = 3000
APP_TITLE = "공공기관 채용 알림"

# 여러 개 고르는 조건: (쿼리 키, API 파라미터, 코드표, 라벨)
MULTI_FILTERS = [
    ("rgn", "workRgnLst", REGIONS, "근무 지역"),
    ("hire", "hireTypeLst", HIRE_TYPES, "고용 형태"),
    ("ncs", "ncsCdLst", NCS, "직무 분야"),
    ("edu", "acbgCondLst", EDUCATIONS, "학력"),
]
# 조건이 바뀌면 지워야 하는 세션 값 (브라우저 저장 기록 saved 는 유지)
SESSION_KEYS = ("check", "postings", "seen_sn", "new", "new_title", "open_sn", "notify", "map_rgn")
# 관심 공고는 목록에서 사라져도 보여줄 수 있게 이 필드만 브라우저에 저장한다
SNAPSHOT_KEYS = ("recrutPblntSn", "recrutPbancTtl", "instNm", "workRgnNmLst", "hireTypeNmLst",
                 "recrutSeNm", "recrutNope", "pbancEndYmd", "srcUrl")
VIEWS = {"list": "목록", "map": "지도", "swipe": "넘겨보기", "star": "관심"}
# 시도 경계: Natural Earth admin-1 (퍼블릭 도메인)을 단순화해 SVG 경로로 바꾼 것
KOREA_MAP = json.loads(Path(__file__).with_name("korea_map.json").read_text(encoding="utf-8"))
MAP_TONES = ("gray-200", "carrot-100", "carrot-200", "carrot-300", "carrot-400", "carrot-500")

# SEED Design (당근, Apache-2.0) 공식 CSS + Pretendard (OFL)
SEED_CSS = "https://cdn.jsdelivr.net/npm/@seed-design/css@3.0.3"
CSS = f"""
<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css");
@import url("{SEED_CSS}/base.min.css");
@import url("{SEED_CSS}/recipes/list-item.css");
@import url("{SEED_CSS}/recipes/badge.css");

.stApp *:not([data-testid="stIconMaterial"]) {{
  font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 760px; padding: 48px 20px 80px; }}

/* 머리말 */
.page-title {{ font-size: var(--seed-font-size-t10); line-height: var(--seed-line-height-t10);
  font-weight: var(--seed-font-weight-bold); color: var(--seed-color-fg-neutral); letter-spacing: -0.02em; margin: 0 0 4px; }}
.lead {{ font-size: var(--seed-font-size-t4); line-height: 1.55; color: var(--seed-color-fg-neutral-subtle); margin: 0; }}

/* 확인 시각 패널 */
.sched {{ background: var(--seed-color-palette-carrot-100); border-radius: var(--seed-radius-r4);
  padding: 22px 22px 18px; margin: 24px 0 0; }}
.sched ol {{ list-style: none; display: flex; margin: 0; padding: 0; }}
.sched li {{ flex: 1; display: flex; flex-direction: column; gap: 12px; position: relative; margin: 0; }}
.sched li::before {{ content: ""; position: absolute; top: 6px; left: 14px; right: 0; height: 2px;
  background: var(--seed-color-palette-carrot-200); }}
.sched li:last-child::before {{ display: none; }}
.sched li.done::before {{ background: var(--seed-color-bg-brand-solid); }}
.sched .dot {{ width: 14px; height: 14px; border-radius: 50%; box-sizing: border-box; position: relative;
  border: 2px solid var(--seed-color-palette-carrot-200); background: var(--seed-color-palette-carrot-100); }}
.sched .done .dot {{ background: var(--seed-color-bg-brand-solid); border-color: var(--seed-color-bg-brand-solid); }}
.sched .next .dot {{ border-color: var(--seed-color-bg-brand-solid); background: #FFFFFF; }}
.sched .time {{ font-size: var(--seed-font-size-t9); line-height: 1; font-weight: var(--seed-font-weight-bold);
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--seed-color-palette-carrot-200); }}
.sched .done .time {{ color: var(--seed-color-fg-neutral); }}
.sched .next .time {{ color: var(--seed-color-fg-brand); }}
.sched p {{ font-size: var(--seed-font-size-t3); line-height: 1.5; color: var(--seed-color-fg-neutral-muted); margin: 16px 0 0; }}

/* 브라우저 알림 줄 */
.notif {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; min-height: 36px; padding: 6px 2px 0; }}
.notif-msg.err {{ flex-basis: 100%; color: var(--seed-color-fg-neutral-muted); }}
.notif-btn {{ border: 1px solid var(--seed-color-stroke-neutral-weak); background: #FFFFFF; color: var(--seed-color-fg-neutral);
  font-size: var(--seed-font-size-t3); font-weight: var(--seed-font-weight-bold); padding: 7px 14px;
  border-radius: var(--seed-radius-full); cursor: pointer; }}
.notif-btn:hover {{ background: var(--seed-color-bg-layer-default-pressed); }}
.notif-msg {{ font-size: var(--seed-font-size-t3); color: var(--seed-color-fg-neutral-subtle); }}
.notif-msg.on::before {{ content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--seed-color-bg-positive-solid); margin: 0 6px 2px 0; }}

/* 섹션 제목 */
.sec-title {{ font-size: var(--seed-font-size-t6); line-height: var(--seed-line-height-t6);
  font-weight: var(--seed-font-weight-bold); color: var(--seed-color-fg-neutral); margin: 28px 0 4px; }}
.sec-title span {{ font-weight: var(--seed-font-weight-regular); color: var(--seed-color-fg-neutral-subtle); margin-left: 4px; }}
.empty {{ font-size: var(--seed-font-size-t4); line-height: 1.6; color: var(--seed-color-fg-neutral-subtle); padding: 16px 0; margin: 0;
  border-bottom: 1px solid var(--seed-color-palette-gray-300); }}

/* 공고 행: SEED list-item + badge */
.job.seed-list-item__root {{ padding-inline: 0; padding-block: 16px; align-items: flex-start; cursor: pointer;
  border-bottom: 1px solid var(--seed-color-palette-gray-300); color: inherit; outline-offset: 2px; }}
.job:hover .seed-list-item__title {{ text-decoration: underline; text-underline-offset: 3px; }}
.job .seed-list-item__content {{ min-width: 0; gap: 4px; }}
.job .seed-list-item__title {{ font-weight: var(--seed-font-weight-bold); letter-spacing: -0.01em; }}
.job .seed-list-item__detail {{ font-size: var(--seed-font-size-t4); line-height: var(--seed-line-height-t4); }}
.job .due {{ font-size: var(--seed-font-size-t3); line-height: var(--seed-line-height-t3); color: var(--seed-color-fg-neutral-muted); }}
.job .seed-list-item__suffix {{ gap: 2px; position: relative; z-index: 1; }}  /* SEED 콘텐츠의 전체 행 눌림 영역 위로 */
.star {{ border: none; background: transparent; cursor: pointer; font-size: 20px; line-height: 1; padding: 4px 2px 4px 6px;
  color: var(--seed-color-palette-gray-500); }}
.star.on {{ color: var(--seed-color-bg-brand-solid); }}

/* 넘겨보기 */
.swipe {{ display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 12px 0 4px; overflow: hidden; }}
.swipe-progress {{ font-size: var(--seed-font-size-t3); color: var(--seed-color-fg-neutral-subtle); font-variant-numeric: tabular-nums; }}
.swipe-card {{ width: 100%; max-width: 440px; box-sizing: border-box; min-height: 300px; padding: 28px 24px 22px;
  display: flex; flex-direction: column; gap: 10px; background: #FFFFFF; cursor: grab; user-select: none; touch-action: pan-y;
  border: 1px solid var(--seed-color-stroke-neutral-weak); border-radius: var(--seed-radius-r5); }}
.swipe-card:active {{ cursor: grabbing; }}
.swipe-card[data-hint="star"] {{ border-color: var(--seed-color-bg-brand-solid); }}
.swipe-card[data-hint="pass"] {{ border-color: var(--seed-color-palette-gray-700); }}
.swipe-new {{ align-self: flex-start; }}
.swipe-inst {{ font-size: var(--seed-font-size-t4); color: var(--seed-color-fg-neutral-subtle); }}
.swipe-title {{ font-size: var(--seed-font-size-t8); line-height: var(--seed-line-height-t8); font-weight: var(--seed-font-weight-bold);
  color: var(--seed-color-fg-neutral); letter-spacing: -0.02em; }}
.swipe-meta {{ font-size: var(--seed-font-size-t4); line-height: 1.6; color: var(--seed-color-fg-neutral-muted); }}
.swipe-foot {{ margin-top: auto; padding-top: 12px; display: flex; justify-content: space-between; align-items: center;
  font-size: var(--seed-font-size-t3); color: var(--seed-color-fg-neutral-muted); }}
.swipe-actions {{ display: flex; gap: 10px; width: 100%; max-width: 440px; }}
.swipe-actions button {{ flex: 1; height: 52px; border: none; cursor: pointer; border-radius: var(--seed-radius-r3);
  font-size: var(--seed-font-size-t5); font-weight: var(--seed-font-weight-bold); }}
.swipe-actions [data-act="pass"] {{ background: var(--seed-color-bg-neutral-weak); color: var(--seed-color-fg-neutral); }}
.swipe-actions [data-act="open"] {{ background: #FFFFFF; color: var(--seed-color-fg-neutral); border: 1px solid var(--seed-color-stroke-neutral-weak); }}
.swipe-actions [data-act="star"] {{ background: var(--seed-color-bg-brand-solid); color: var(--seed-color-fg-on-brand-solid); }}
.swipe-help {{ font-size: var(--seed-font-size-t2); color: var(--seed-color-fg-neutral-subtle); }}

/* 지도 */
.kmap svg {{ width: 100%; height: auto; display: block; max-height: 560px; }}
.kmap path {{ stroke: #FFFFFF; stroke-width: 1.2; cursor: pointer; transition: opacity .15s; }}
.kmap path:hover {{ opacity: .75; }}
.kmap path.sel {{ fill: none; stroke: var(--seed-color-fg-neutral); stroke-width: 2.2; pointer-events: none; }}
.map-legend {{ display: flex; align-items: center; gap: 4px; font-size: var(--seed-font-size-t2); color: var(--seed-color-fg-neutral-subtle); margin-top: 8px; }}
.map-legend i {{ width: 14px; height: 10px; border-radius: 2px; display: inline-block; }}

/* 상세 모달 */
.d-inst {{ font-size: var(--seed-font-size-t4); color: var(--seed-color-fg-neutral-subtle); margin: 0 0 4px; }}
.d-title {{ font-size: var(--seed-font-size-t7); line-height: var(--seed-line-height-t7); font-weight: var(--seed-font-weight-bold);
  color: var(--seed-color-fg-neutral); letter-spacing: -0.02em; margin: 0 0 10px; }}
.d-meta {{ font-size: var(--seed-font-size-t4); line-height: 1.6; color: var(--seed-color-fg-neutral-muted); margin: 0; }}
.d-due {{ display: flex; gap: 8px; align-items: center; font-size: var(--seed-font-size-t4); color: var(--seed-color-fg-neutral); margin: 10px 0 0; }}
.d-sub {{ font-size: var(--seed-font-size-t4); font-weight: var(--seed-font-weight-bold); color: var(--seed-color-fg-neutral); margin: 18px 0 6px; }}
.d-text {{ white-space: pre-wrap; font-size: var(--seed-font-size-t4); line-height: 1.7; color: var(--seed-color-fg-neutral-muted); margin: 0; }}
.d-file {{ display: flex; gap: 10px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--seed-color-palette-gray-300);
  font-size: var(--seed-font-size-t4); }}
.d-file a {{ color: var(--seed-color-fg-neutral); text-decoration: none; word-break: break-all; }}
.d-file a:hover {{ text-decoration: underline; }}

/* Streamlit 위젯을 SEED 모양으로 */
.stButton button, .stFormSubmitButton button, .stLinkButton a {{ border-radius: var(--seed-radius-r2_5); border: none; min-height: 40px;
  background: var(--seed-color-bg-neutral-weak); color: var(--seed-color-fg-neutral); font-weight: var(--seed-font-weight-bold); }}
.stButton button:hover, .stFormSubmitButton button:hover {{ background: var(--seed-color-bg-neutral-weak-pressed); color: var(--seed-color-fg-neutral); }}
.stFormSubmitButton button[kind="primaryFormSubmit"], .stButton button[kind="primary"], .stLinkButton a[kind="primary"] {{ min-height: 48px;
  background: var(--seed-color-bg-brand-solid); color: var(--seed-color-fg-on-brand-solid); font-size: var(--seed-font-size-t5); }}
.stFormSubmitButton button[kind="primaryFormSubmit"]:hover, .stLinkButton a[kind="primary"]:hover {{
  background: var(--seed-color-bg-brand-solid-pressed); color: #FFFFFF; }}

[data-testid="stWidgetLabel"] p {{ font-size: var(--seed-font-size-t5); font-weight: var(--seed-font-weight-bold);
  color: var(--seed-color-fg-neutral); }}
[data-testid="stButtonGroup"] {{ gap: 8px; }}
[data-testid="stButtonGroup"] button[data-variant="pills"] {{
  border-radius: var(--seed-radius-full); min-height: 36px; padding: 0 14px;
  font-size: var(--seed-font-size-t4); font-weight: var(--seed-font-weight-medium);
  background: #FFFFFF; color: var(--seed-color-fg-neutral); border: 1px solid var(--seed-color-stroke-neutral-weak); }}
[data-testid="stButtonGroup"] button[data-variant="pills"]:hover {{ background: var(--seed-color-bg-layer-default-pressed);
  color: var(--seed-color-fg-neutral); border-color: var(--seed-color-stroke-neutral-weak); }}
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected="true"] {{
  background: var(--seed-color-bg-neutral-inverted); color: var(--seed-color-fg-neutral-inverted);
  border-color: var(--seed-color-bg-neutral-inverted); }}
[data-testid="stButtonGroup"] button[data-variant="pills"] p {{ font-size: inherit; font-weight: inherit; color: inherit; }}
.st-key-view {{ margin-top: 20px; }}
.st-key-map_pills [role="radiogroup"] {{ flex-wrap: wrap; overflow: visible; }}
.st-key-view button[data-variant="pills"] {{ min-height: 40px; padding: 0 18px; font-size: var(--seed-font-size-t5); }}
[data-testid="stTextInput"] [data-baseweb="input"] {{ border-radius: var(--seed-radius-r2_5); background: #FFFFFF;
  border: 1px solid var(--seed-color-stroke-neutral-weak); min-height: 48px; }}
[data-testid="stTextInput"] input {{ background: #FFFFFF; font-size: var(--seed-font-size-t5); }}
[data-testid="stForm"] [data-testid="stVerticalBlock"] {{ gap: 28px; }}
[data-testid="stTabs"] button p {{ font-size: var(--seed-font-size-t4); font-weight: var(--seed-font-weight-bold); }}

@media (max-width: 480px) {{
  .block-container {{ padding: 24px 16px 64px; }}
  .sched {{ padding: 18px 16px 14px; }}
  .sched .time {{ font-size: var(--seed-font-size-t7); }}
  .st-key-view button[data-variant="pills"] {{ padding: 0 14px; font-size: var(--seed-font-size-t4); }}
  .kmap svg {{ max-height: 360px; margin: 0 auto; }}
  .map-legend {{ justify-content: center; }}
}}
</style>
"""


# ───────────────────────── 데이터 ─────────────────────────

def get_api_key() -> str:
    """로컬에서는 .env, Streamlit Cloud에서는 Secrets 에서 키를 읽는다."""
    load_dotenv()
    key = os.getenv("DATA_GO_KR_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets["DATA_GO_KR_API_KEY"]).strip()
    except Exception:
        return ""


def last_check(now: datetime) -> datetime:
    """가장 최근에 지난 확인 시각 (9시 전이면 어제 18시)."""
    for hour in reversed(CHECK_HOURS):
        t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if t <= now:
            return t
    yesterday = now - timedelta(days=1)
    return yesterday.replace(hour=CHECK_HOURS[-1], minute=0, second=0, microsecond=0)


def next_check(now: datetime) -> datetime:
    for hour in CHECK_HOURS:
        t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if t > now:
            return t
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=CHECK_HOURS[0], minute=0, second=0, microsecond=0)


@st.cache_data(ttl=timedelta(hours=6), show_spinner="공고를 불러오는 중이에요")
def load_postings(check_key: str, filters: dict) -> list[dict]:
    # check_key 는 확인 시각마다 캐시를 새로 만들기 위한 값이다.
    # 같은 시각, 같은 조건이면 여러 사용자가 한 번의 API 호출 결과를 같이 쓴다.
    return fetch_ongoing(get_api_key(), filters)


@st.cache_data(ttl=timedelta(hours=6), show_spinner="상세 정보를 불러오는 중이에요")
def load_detail(sn: int) -> dict:
    return fetch_detail(get_api_key(), sn)


def read_filters() -> dict:
    """URL 쿼리 파라미터 → API 파라미터."""
    qp = st.query_params
    filters = {api: qp.get(key, "") for key, api, _, _ in MULTI_FILTERS}
    filters["recrutSe"] = qp.get("se", "")
    filters["recrutPbancTtl"] = qp.get("q", "")
    return filters


def describe(filters: dict) -> str:
    """지금 조건을 한 문장으로."""
    def names(api: str, codes: dict) -> str:
        return ", ".join(codes.get(c, c) for c in filters[api].split(",") if c)

    words = []
    if filters["workRgnLst"]:
        words.append(f"{names('workRgnLst', REGIONS)} 근무")
    if filters["hireTypeLst"]:
        words.append(names("hireTypeLst", HIRE_TYPES))
    if filters["recrutSe"]:
        words.append(RECRUIT_KINDS.get(filters["recrutSe"], ""))
    if filters["ncsCdLst"]:
        words.append(f"{names('ncsCdLst', NCS)} 분야")
    if filters["acbgCondLst"]:
        words.append(f"학력 {names('acbgCondLst', EDUCATIONS)}")
    target = " ".join(words) + " 공고" if words else "진행 중인 모든 공고"
    if filters["recrutPbancTtl"]:
        target = f"제목에 ‘{filters['recrutPbancTtl']}’이(가) 들어간 {target}"
    return f"{target}를 보고 있어요."


# ───────────────────────── 브라우저 저장 기록 ─────────────────────────

def parse_saved(raw: str) -> dict:
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    return {
        "seen": int(data.get("seen") or 0),
        "stars": dict(data.get("stars") or {}),
        "passed": [int(x) for x in data.get("passed") or []],
    }


def is_starred(sn: int) -> bool:
    return str(sn) in st.session_state.saved["stars"]


def toggle_star(p: dict) -> None:
    saved = st.session_state.saved
    key = str(p["recrutPblntSn"])
    if key in saved["stars"]:
        del saved["stars"][key]
        st.toast("관심 공고에서 뺐어요.")
    else:
        saved["stars"][key] = {k: p.get(k) for k in SNAPSHOT_KEYS}
        saved["passed"] = [x for x in saved["passed"] if x != p["recrutPblntSn"]]
        st.toast("관심 공고에 담았어요.")


def mark_passed(sn: int) -> None:
    saved = st.session_state.saved
    if sn not in saved["passed"]:
        saved["passed"] = (saved["passed"] + [sn])[-PASSED_LIMIT:]


def find_posting(sn: int) -> dict | None:
    for p in st.session_state.get("postings", []):
        if p["recrutPblntSn"] == sn:
            return p
    return st.session_state.saved["stars"].get(str(sn))


# ───────────────────────── HTML 조각 ─────────────────────────

def schedule_html(now: datetime) -> str:
    nxt = next_check(now)
    items = []
    for hour in CHECK_HOURS:
        t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        state = "done" if t <= now else ("next" if t == nxt else "later")
        items.append(f'<li class="{state}"><span class="dot"></span><span class="time">{hour:02d}:00</span></li>')
    when = "내일 " if nxt.date() != now.date() else ""
    note = f"다음 확인은 {when}{nxt.hour}시예요. 이 페이지를 켜두면 새 공고가 올라왔을 때 알려드려요."
    return f'<section class="sched"><ol>{"".join(items)}</ol><p>{note}</p></section>'


def d_day(p: dict) -> int | None:
    end = p.get("pbancEndYmd") or ""
    if len(end) != 8:
        return None
    today = datetime.now(KST).date()
    return (date(int(end[:4]), int(end[4:6]), int(end[6:8])) - today).days


def due_text(p: dict) -> str:
    end = p.get("pbancEndYmd") or ""
    return f"{int(end[4:6])}월 {int(end[6:8])}일 마감" if len(end) == 8 else ""


def summary(p: dict) -> str:
    """'한국전력공사에서 서울 근무 정규직(신입) 3명을 뽑아요.' (escape 된 문자열)"""
    regions = [r for r in (p.get("workRgnNmLst") or "").split(",") if r]
    region = ", ".join(regions[:3]) + (f" 외 {len(regions) - 3}곳" if len(regions) > 3 else "")
    hire = (p.get("hireTypeNmLst") or "").replace(",", ", ")
    kind = p.get("recrutSeNm") or ""
    who = f"{hire}({kind})" if hire and kind else (hire or kind)
    count = f"{p['recrutNope']}명을" if p.get("recrutNope") else "인원을"
    detail = " ".join(x for x in (f"{region} 근무" if region else "", who, count) if x)
    return f"{html.escape(p.get('instNm') or '')}에서 {html.escape(detail)} 뽑아요."


def badge_html(d: int | None) -> str:
    if d is None:
        return ""
    tone = "critical" if d <= 3 else "neutral"
    label = "마감" if d < 0 else ("D-Day" if d == 0 else f"D-{d}")
    return (f'<span class="seed-badge__root seed-badge__root--size_medium seed-badge__root--variant_weak '
            f'seed-badge__root--tone_{tone}-variant_weak"><span class="seed-badge__label">{label}</span></span>')


def row_html(p: dict) -> str:
    """공고 한 줄. SEED list-item 구조. 행을 누르면 상세, ☆를 누르면 관심."""
    sn = int(p["recrutPblntSn"])
    on = is_starred(sn)
    star = (f'<button type="button" class="star{" on" if on else ""}" data-star="{sn}" '
            f'aria-label="{"관심 해제" if on else "관심에 담기"}">{"★" if on else "☆"}</button>')
    return (
        f'<div class="job seed-list-item__root" data-open="{sn}" role="button" tabindex="0">'
        f'<span class="seed-list-item__content">'
        f'<span class="seed-list-item__title">{html.escape(p.get("recrutPbancTtl") or "제목 없음")}</span>'
        f'<span class="seed-list-item__detail">{summary(p)}</span><span class="due">{due_text(p)}</span></span>'
        f'<span class="seed-list-item__suffix">{badge_html(d_day(p))}{star}</span></div>'
    )


def card_html(p: dict, done: int, total: int, is_new: bool) -> str:
    new = ('<span class="swipe-new seed-badge__root seed-badge__root--size_medium seed-badge__root--variant_weak '
           'seed-badge__root--tone_brand-variant_weak"><span class="seed-badge__label">새 공고</span></span>') if is_new else ""
    return (
        f'<div class="swipe-progress">{done + 1} / {total}</div>'
        f'<div class="swipe-card">{new}'
        f'<div class="swipe-inst">{html.escape(p.get("instNm") or "")}</div>'
        f'<div class="swipe-title">{html.escape(p.get("recrutPbancTtl") or "")}</div>'
        f'<div class="swipe-meta">{summary(p)}</div>'
        f'<div class="swipe-foot"><span>{due_text(p)}</span>{badge_html(d_day(p))}</div></div>'
        '<div class="swipe-actions"><button type="button" data-act="pass">패스</button>'
        '<button type="button" data-act="open">자세히</button>'
        '<button type="button" data-act="star">관심</button></div>'
        '<div class="swipe-help">카드를 오른쪽으로 밀면 관심, 왼쪽으로 밀면 패스예요. 키보드 ← → 도 돼요.</div>'
    )


def map_svg(counts: dict[str, int], selected: str | None) -> str:
    top = max(counts.values(), default=0)
    # 큰 지역을 먼저 그려야 서울, 대전처럼 안에 있는 지역이 위에 보인다
    regions = sorted(KOREA_MAP["regions"].items(), key=lambda kv: -len(kv[1]["d"]))
    paths = []
    for code, r in regions:
        c = counts.get(code, 0)
        level = 0 if not c or not top else max(1, math.ceil(5 * c / top))
        paths.append(f'<path data-rgn="{code}" d="{r["d"]}" style="fill: var(--seed-color-palette-{MAP_TONES[level]})">'
                     f'<title>{REGIONS[code]} {c}건</title></path>')
    if selected in KOREA_MAP["regions"]:  # 선택 테두리는 맨 위에 따로 그려서 안쪽 지역을 가리지 않는다
        paths.append(f'<path class="sel" d="{KOREA_MAP["regions"][selected]["d"]}"/>')
    legend = "".join(f'<i style="background: var(--seed-color-palette-{t})"></i>' for t in MAP_TONES)
    return (f'<svg viewBox="{KOREA_MAP["viewBox"]}" role="img" aria-label="지역별 공고 수 지도">{"".join(paths)}</svg>'
            f'<div class="map-legend">적음 {legend} 많음</div>')


def section(title: str, count: int) -> None:
    st.html(f'<h2 class="sec-title">{html.escape(title)} <span>{count}건</span></h2>')


def set_tab_title(new_count: int) -> None:
    title = f"({new_count}) {APP_TITLE}" if new_count else APP_TITLE
    st.html(f"<script>document.title = {json.dumps(title)};</script>", unsafe_allow_javascript=True)


# ───────────────────────── 상세 모달 ─────────────────────────

def _close_detail() -> None:
    st.session_state.pop("open_sn", None)


@st.dialog("공고 상세", width="large", on_dismiss=_close_detail)
def detail_dialog(sn: int) -> None:
    base = find_posting(sn) or {}
    try:
        p = {**base, **load_detail(sn)}
    except Exception as e:
        if not base:
            st.error(f"상세 정보를 불러오지 못했어요. ({e})")
            return
        p = base
        st.warning("상세 정보를 불러오지 못해서 저장된 정보만 보여드려요.")

    st.html(
        f'<p class="d-inst">{html.escape(p.get("instNm") or "")}</p>'
        f'<h2 class="d-title">{html.escape(p.get("recrutPbancTtl") or "")}</h2>'
        f'<p class="d-meta">{summary(p)}</p>'
        f'<p class="d-due">{badge_html(d_day(p))}<span>{due_text(p)}</span></p>'
    )

    def text(value: str | None, empty: str) -> None:
        st.html(f'<p class="d-text">{html.escape((value or "").strip() or empty)}</p>')

    qual, pref, steps, files = st.tabs(["자격요건", "우대사항", "전형절차", "첨부파일"])
    with qual:
        text(p.get("aplyQlfcCn"), "공고문에서 확인해 주세요.")
        if p.get("acbgCondNmLst"):
            st.html(f'<p class="d-sub">학력</p><p class="d-text">{html.escape(p["acbgCondNmLst"])}</p>')
        if p.get("disqlfcRsn"):
            st.html('<p class="d-sub">결격사유</p>')
            text(p["disqlfcRsn"], "")
    with pref:
        text(p.get("prefCn") or p.get("prefCondCn"), "따로 적힌 우대사항이 없어요.")
    with steps:
        fields = [s.get("recrutPbancTtl") for s in p.get("steps") or [] if s.get("recrutPbancTtl")]
        if fields:
            st.html('<p class="d-sub">모집 분야</p>')
            text("\n".join(f"• {f}" for f in fields), "")
            st.html('<p class="d-sub">전형 방법</p>')
        text(p.get("scrnprcdrMthdExpln"), "공고문에서 확인해 주세요.")
    with files:
        rows = [
            f'<div class="d-file"><span class="seed-badge__root seed-badge__root--size_medium seed-badge__root--variant_weak '
            f'seed-badge__root--tone_neutral-variant_weak"><span class="seed-badge__label">'
            f'{FILE_TYPES.get(f.get("atchFileType"), "기타")}</span></span>'
            f'<a href="{html.escape(f["url"], quote=True)}" target="_blank" rel="noopener">{html.escape(f.get("atchFileNm") or "첨부파일")}</a></div>'
            for f in p.get("files") or [] if str(f.get("url", "")).startswith("http")
        ]
        if rows:
            st.html("".join(rows))
        else:
            text(p.get("nonatchRsn"), "첨부파일이 없어요.")

    left, right = st.columns(2)
    starred = is_starred(sn)
    if left.button("관심 해제" if starred else "☆ 관심에 담기", width="stretch", key="d_star"):
        toggle_star(p)
        st.rerun()
    url = p.get("srcUrl") or ""
    if url.startswith("http"):
        right.link_button("원문 공고 보기", url, type="primary", width="stretch")


# ───────────────────────── 보기 ─────────────────────────

def rerun_board() -> None:
    """보드(fragment)만 다시 그린다. 페이지 전체가 실행 중일 때는 전체를 다시 실행한다."""
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitInvalidLayoutContextError:
        st.rerun()


def handle_action(action: dict | None) -> None:
    """목록, 넘겨보기, 지도 컴포넌트에서 온 클릭을 처리한다."""
    if not action:
        return
    sn = int(action.get("sn") or 0)
    kind = action.get("type")
    if kind == "open":
        st.session_state.open_sn = sn
        return
    p = find_posting(sn)
    if kind == "star" and p:
        toggle_star(p)
    elif kind == "pass":
        mark_passed(sn)
    rerun_board()


def posting_list(posts: list[dict], key: str, empty: str) -> None:
    if not posts:
        st.html(f'<p class="empty">{html.escape(empty)}</p>')
        return
    shown = st.session_state.setdefault(f"shown_{key}", PAGE_STEP)
    handle_action(widgets.job_list("".join(row_html(p) for p in posts[:shown]), key=f"list_{key}"))
    if len(posts) > shown:
        if st.button(f"더 보기 ({len(posts) - shown}건 남음)", width="stretch", key=f"more_{key}"):
            st.session_state[f"shown_{key}"] = shown + PAGE_STEP
            rerun_board()


def list_view(postings: list[dict]) -> None:
    ss = st.session_state
    section(ss.new_title, len(ss.new))
    posting_list(ss.new, "new", f"{ss.new_title}는 아직 없어요.")

    section("진행 중인 공고", len(postings))
    order = st.pills("정렬", ["최신 공고순", "마감 임박순"], default="최신 공고순",
                     label_visibility="collapsed", key="sort")
    if order == "마감 임박순":
        postings = sorted(postings, key=lambda p: (p.get("pbancEndYmd") or "99999999", -p["recrutPblntSn"]))
    else:
        postings = sorted(postings, key=lambda p: -p["recrutPblntSn"])
    posting_list(postings, "all", "조건에 맞는 진행 중 공고가 없어요. 조건을 넓혀 보세요.")


def map_view(postings: list[dict]) -> None:
    ss = st.session_state
    counts: dict[str, int] = {}
    for p in postings:
        for code in (p.get("workRgnLst") or "").split(","):
            if code in REGIONS:
                counts[code] = counts.get(code, 0) + 1

    selected = ss.get("map_rgn")
    left, right = st.columns([5, 6], gap="large")
    with left:
        clicked = widgets.korea_map(map_svg(counts, selected))
        if clicked and clicked.get("code") != selected:
            ss.map_rgn = ss.map_pills = clicked["code"]
            ss.pop("shown_map", None)
            rerun_board()
    with right:
        st.html('<p class="lead">지도에서 지역을 누르거나 아래에서 골라주세요. 색이 진할수록 공고가 많아요.</p>')
        options = [c for c in REGIONS if counts.get(c)]
        if ss.get("map_pills") not in options:
            ss.pop("map_pills", None)
        picked = st.pills("지역", options, format_func=lambda c: f"{REGIONS[c]} {counts[c]}",
                          label_visibility="collapsed", key="map_pills")
        if picked != selected:
            ss.map_rgn = picked
            ss.pop("shown_map", None)
            rerun_board()

    if not selected:
        return
    in_region = sorted((p for p in postings if selected in (p.get("workRgnLst") or "").split(",")),
                       key=lambda p: -p["recrutPblntSn"])
    section(f"{REGIONS[selected]} 근무 공고", len(in_region))
    posting_list(in_region, "map", "이 지역에는 진행 중인 공고가 없어요.")


def swipe_view(postings: list[dict]) -> None:
    ss = st.session_state
    decided = set(ss.saved["passed"]) | {int(k) for k in ss.saved["stars"]}
    new_sns = {p["recrutPblntSn"] for p in ss.new}
    queue = sorted((p for p in postings if p["recrutPblntSn"] not in decided),
                   key=lambda p: (p["recrutPblntSn"] not in new_sns, -p["recrutPblntSn"]))
    if not queue:
        st.html('<p class="empty">지금 조건의 공고를 모두 살펴봤어요. 다음 확인 시각에 새 공고가 오면 여기에 다시 쌓여요.</p>')
        passed_here = [p["recrutPblntSn"] for p in postings if p["recrutPblntSn"] in set(ss.saved["passed"])]
        if passed_here and st.button(f"패스한 공고 {len(passed_here)}건 다시 보기", width="stretch"):
            ss.saved["passed"] = [x for x in ss.saved["passed"] if x not in set(passed_here)]
            rerun_board()
        return
    p = queue[0]
    done = len(postings) - len(queue)
    handle_action(widgets.swipe_card(card_html(p, done, len(postings), p["recrutPblntSn"] in new_sns),
                                     p["recrutPblntSn"]))


def star_view() -> None:
    stars = sorted(st.session_state.saved["stars"].values(),
                   key=lambda p: (p.get("pbancEndYmd") or "99999999", -int(p["recrutPblntSn"])))
    section("관심 공고", len(stars))
    posting_list(stars, "star", "아직 관심 공고가 없어요. 넘겨보기나 목록에서 ☆를 눌러 모아보세요.")


@st.fragment(run_every=timedelta(seconds=60))
def live_board(filters: dict) -> None:
    """1분마다 시계만 확인하고, 확인 시각이 바뀌었을 때만 API를 다시 부른다."""
    ss = st.session_state

    # 브라우저 저장 기록: 처음에는 읽고, 그다음부터는 매번 지금 상태를 써 둔다
    raw = widgets.browser_store(json.dumps(ss.saved, ensure_ascii=False) if "saved" in ss else None)
    if "saved" not in ss:
        if raw is None and not ss.get("store_waited"):
            # 보통 곧바로 응답이 온다. 다음 갱신(1분)까지 응답이 없으면 기록 없이 시작한다.
            ss.store_waited = True
            st.html('<p class="lead" style="margin-top:24px">기록을 불러오는 중이에요.</p>')
            return
        ss.saved = parse_saved(raw or "")

    now = datetime.now(KST)
    check = last_check(now)
    if ss.get("check") != check:
        try:
            postings = load_postings(check.isoformat(), filters)
        except Exception as e:
            st.error(f"공고를 불러오지 못했어요. 잠시 후 다시 시도해 주세요. ({e})")
            return
        top = max((p["recrutPblntSn"] for p in postings), default=0)
        first_run = "check" not in ss
        if first_run and ss.saved["seen"]:
            ss.new = [p for p in postings if p["recrutPblntSn"] > ss.saved["seen"]]
            ss.new_title = "지난 방문 이후 새로 올라온 공고"
        elif first_run:
            today = now.strftime("%Y%m%d")
            ss.new = [p for p in postings if p.get("pbancBgngYmd") == today]
            ss.new_title = "오늘 올라온 공고"
        else:
            ss.new = [p for p in postings if p["recrutPblntSn"] > ss.seen_sn]
            ss.new_title = f"{check.hour}시 확인에서 새로 올라온 공고"
            if ss.new:
                first = ss.new[0].get("instNm") or ""
                more = f" 외 {len(ss.new) - 1}건" if len(ss.new) > 1 else ""
                st.toast(f"새 공고가 올라왔어요. {first}{more}", duration="long")
                ss.notify = {"id": f"{check:%Y%m%d%H}:{len(ss.new)}:{top}",
                             "title": f"새 공고 {len(ss.new)}건이 올라왔어요", "body": f"{first}{more}"}
        ss.check = check
        ss.postings = postings
        ss.seen_sn = max(top, ss.get("seen_sn", 0))
        ss.saved["seen"] = max(ss.saved["seen"], top)
        if first_run:
            rerun_board()  # 바뀐 '마지막으로 본 공고번호'를 바로 브라우저에 저장

    postings = ss.postings
    set_tab_title(len(ss.new))
    st.html(schedule_html(now))
    widgets.notifier(ss.get("notify"))

    decided = set(ss.saved["passed"]) | {int(k) for k in ss.saved["stars"]}
    left = sum(p["recrutPblntSn"] not in decided for p in postings)
    labels = {"list": "목록", "map": "지도", "swipe": f"넘겨보기 {left}", "star": f"관심 {len(ss.saved['stars'])}"}
    view = st.pills("보기", list(VIEWS), format_func=labels.get, default="list",
                    label_visibility="collapsed", key="view") or "list"

    if view == "map":
        map_view(postings)
    elif view == "swipe":
        swipe_view(postings)
    elif view == "star":
        star_view()
    else:
        list_view(postings)

    if ss.get("open_sn"):
        detail_dialog(ss.open_sn)


# ───────────────────────── 화면 ─────────────────────────

def setup_screen() -> None:
    st.html(f'<div class="page-title" role="heading" aria-level="1">{APP_TITLE}</div>'
            '<p class="lead">관심 있는 조건을 눌러 골라주세요. 아무것도 고르지 않으면 전체 공고를 보여드려요. '
            '고른 조건은 주소에 저장되니 북마크해 두면 다음에도 그대로 열려요.</p>')
    qp = st.query_params
    with st.form("setup", border=False):
        picked: dict[str, str] = {}
        for key, _, codes, label in MULTI_FILTERS:
            default = [c for c in qp.get(key, "").split(",") if c in codes]
            chosen = st.pills(label, list(codes), selection_mode="multi", default=default,
                              format_func=codes.get)
            picked[key] = ",".join(chosen)
        current = qp.get("se", "")
        picked["se"] = st.pills("채용 구분", list(RECRUIT_KINDS), format_func=RECRUIT_KINDS.get,
                                default=current if current in RECRUIT_KINDS else None) or ""
        picked["q"] = st.text_input("공고 제목에 들어갈 단어", value=qp.get("q", ""),
                                    placeholder="예: 행정, 전산").strip()
        if st.form_submit_button("이 조건으로 시작하기", type="primary", width="stretch"):
            st.query_params.from_dict({"ok": "1", **{k: v for k, v in picked.items() if v}})
            for k in SESSION_KEYS:
                st.session_state.pop(k, None)
            st.rerun()


def main_screen() -> None:
    filters = read_filters()
    title_col, button_col = st.columns([4, 1], vertical_alignment="bottom")
    with title_col:
        st.html(f'<div class="page-title" role="heading" aria-level="1">{APP_TITLE}</div>'
                f'<p class="lead">{html.escape(describe(filters))}</p>')
    with button_col:
        if st.button("조건 바꾸기", width="stretch"):
            del st.query_params["ok"]
            st.rerun()
    live_board(filters)


st.set_page_config(page_title=APP_TITLE, page_icon="📋", layout="centered")
st.html(CSS)
# SEED 토큰을 OS 다크 모드와 상관없이 라이트로 고정 (Streamlit 테마도 라이트)
st.html('<script>document.documentElement.dataset.seedColorMode = "light-only";</script>',
        unsafe_allow_javascript=True)

if not get_api_key():
    st.error("API 키가 없어요. 로컬에서는 .env, Streamlit Cloud에서는 Secrets에 DATA_GO_KR_API_KEY 를 넣어주세요.")
    st.stop()

if st.query_params.get("ok") == "1":
    main_screen()
else:
    setup_screen()
