"""공공기관 채용 알림 (Streamlit).

한국 시간 9시, 13시, 18시에 진행 중인 공고를 다시 확인하고,
페이지를 켜둔 사람에게 새로 올라온 공고를 알려준다.
조건(필터)은 URL 쿼리 파라미터에 저장되므로 북마크하면 그대로 다시 열린다.

실행: streamlit run app.py
"""
import html
import json
import os
from datetime import datetime, timedelta, timezone

import streamlit as st
from dotenv import load_dotenv

from jobs import EDUCATIONS, HIRE_TYPES, NCS, RECRUIT_KINDS, REGIONS, fetch_ongoing

KST = timezone(timedelta(hours=9))
CHECK_HOURS = (9, 13, 18)
PAGE_STEP = 30
APP_TITLE = "공공기관 채용 알림"

# 여러 개 고르는 조건: (쿼리 키, API 파라미터, 코드표, 라벨)
MULTI_FILTERS = [
    ("rgn", "workRgnLst", REGIONS, "근무 지역"),
    ("hire", "hireTypeLst", HIRE_TYPES, "고용 형태"),
    ("ncs", "ncsCdLst", NCS, "직무 분야"),
    ("edu", "acbgCondLst", EDUCATIONS, "학력"),
]
# 조건이 바뀌면 지워야 하는 세션 값
SESSION_KEYS = ("check", "postings", "seen_sn", "new", "new_title", "shown")

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
.block-container {{ max-width: 720px; padding: 48px 20px 80px; }}

/* 머리말 */
.page-title {{ font-size: var(--seed-font-size-t10); line-height: var(--seed-line-height-t10);
  font-weight: var(--seed-font-weight-bold); color: var(--seed-color-fg-neutral); letter-spacing: -0.02em; margin: 0 0 4px; }}
.lead {{ font-size: var(--seed-font-size-t4); line-height: 1.55; color: var(--seed-color-fg-neutral-subtle); margin: 0; }}

/* 확인 시각 패널: 브랜드 색은 여기에만 */
.sched {{ background: var(--seed-color-palette-carrot-100); border-radius: var(--seed-radius-r4);
  padding: 22px 22px 18px; margin: 24px 0 8px; }}
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

/* 섹션 제목 */
.sec-title {{ font-size: var(--seed-font-size-t6); line-height: var(--seed-line-height-t6);
  font-weight: var(--seed-font-weight-bold); color: var(--seed-color-fg-neutral); margin: 36px 0 4px; }}
.sec-title span {{ font-weight: var(--seed-font-weight-regular); color: var(--seed-color-fg-neutral-subtle); margin-left: 4px; }}
.empty {{ font-size: var(--seed-font-size-t4); color: var(--seed-color-fg-neutral-subtle); padding: 16px 0; margin: 0;
  border-bottom: 1px solid var(--seed-color-palette-gray-300); }}

/* 공고 행: SEED list-item + badge */
.job.seed-list-item__root {{ padding-inline: 0; padding-block: 16px; align-items: flex-start;
  border-bottom: 1px solid var(--seed-color-palette-gray-300); text-decoration: none; color: inherit; }}
a.job:hover .seed-list-item__title {{ text-decoration: underline; text-underline-offset: 3px; }}
.job .seed-list-item__content {{ min-width: 0; gap: 4px; }}
.job .seed-list-item__title {{ font-weight: var(--seed-font-weight-bold); letter-spacing: -0.01em; }}
.job .seed-list-item__detail {{ font-size: var(--seed-font-size-t4); line-height: var(--seed-line-height-t4); }}
.job .due {{ font-size: var(--seed-font-size-t3); line-height: var(--seed-line-height-t3); color: var(--seed-color-fg-neutral-muted); }}
.job .seed-list-item__suffix {{ padding-top: 2px; }}

/* Streamlit 위젯을 SEED 모양으로 */
.stButton button, .stFormSubmitButton button {{ border-radius: var(--seed-radius-r2_5); border: none; min-height: 40px;
  background: var(--seed-color-bg-neutral-weak); color: var(--seed-color-fg-neutral); font-weight: var(--seed-font-weight-bold); }}
.stButton button:hover, .stFormSubmitButton button:hover {{ background: var(--seed-color-bg-neutral-weak-pressed); color: var(--seed-color-fg-neutral); }}
.stFormSubmitButton button[kind="primaryFormSubmit"], .stButton button[kind="primary"] {{ min-height: 52px;
  background: var(--seed-color-bg-brand-solid); color: var(--seed-color-fg-on-brand-solid); font-size: var(--seed-font-size-t5); }}
.stFormSubmitButton button[kind="primaryFormSubmit"]:hover {{ background: var(--seed-color-bg-brand-solid-pressed); color: #FFFFFF; }}

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
[data-testid="stTextInput"] [data-baseweb="input"] {{ border-radius: var(--seed-radius-r2_5); background: #FFFFFF;
  border: 1px solid var(--seed-color-stroke-neutral-weak); min-height: 48px; }}
[data-testid="stTextInput"] input {{ background: #FFFFFF; font-size: var(--seed-font-size-t5); }}
[data-testid="stForm"] [data-testid="stVerticalBlock"] {{ gap: 28px; }}

@media (max-width: 480px) {{
  .block-container {{ padding: 24px 16px 64px; }}
  .sched {{ padding: 18px 16px 14px; }}
  .sched .time {{ font-size: var(--seed-font-size-t7); }}
}}
</style>
"""


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


def posting_html(p: dict) -> str:
    """공고 한 줄. SEED list-item 구조에 D-day는 SEED badge."""
    esc = html.escape
    title = esc(p.get("recrutPbancTtl") or "제목 없음")
    url = p.get("srcUrl") or ""

    regions = [r for r in (p.get("workRgnNmLst") or "").split(",") if r]
    region = ", ".join(regions[:3]) + (f" 외 {len(regions) - 3}곳" if len(regions) > 3 else "")
    hire = (p.get("hireTypeNmLst") or "").replace(",", ", ")
    kind = p.get("recrutSeNm") or ""
    who = f"{hire}({kind})" if hire and kind else (hire or kind)
    count = f"{p['recrutNope']}명을" if p.get("recrutNope") else "인원을"
    detail = " ".join(x for x in (f"{region} 근무" if region else "", who, count) if x)
    meta = f"{esc(p.get('instNm') or '')}에서 {esc(detail)} 뽑아요."

    end = p.get("pbancEndYmd") or ""
    due = f"{int(end[4:6])}월 {int(end[6:8])}일 마감" if len(end) == 8 else ""
    d = p.get("decimalDay")
    badge = ""
    if d is not None:
        tone = "critical" if d <= 3 else "neutral"
        label = "D-Day" if d <= 0 else f"D-{d}"
        badge = (f'<span class="seed-badge__root seed-badge__root--size_medium seed-badge__root--variant_weak '
                 f'seed-badge__root--tone_{tone}-variant_weak"><span class="seed-badge__label">{label}</span></span>')

    body = (
        f'<span class="seed-list-item__content"><span class="seed-list-item__title">{title}</span>'
        f'<span class="seed-list-item__detail">{meta}</span><span class="due">{due}</span></span>'
        f'<span class="seed-list-item__suffix">{badge}</span>'
    )
    if url.startswith("http"):
        return (f'<a class="job seed-list-item__root" href="{esc(url, quote=True)}" '
                f'target="_blank" rel="noopener">{body}</a>')
    return f'<div class="job seed-list-item__root">{body}</div>'


def section(title: str, count: int) -> None:
    st.html(f'<h2 class="sec-title">{html.escape(title)} <span>{count}건</span></h2>')


def set_tab_title(new_count: int) -> None:
    title = f"({new_count}) {APP_TITLE}" if new_count else APP_TITLE
    st.html(f"<script>document.title = {json.dumps(title)};</script>", unsafe_allow_javascript=True)


@st.fragment(run_every=timedelta(seconds=60))
def live_board(filters: dict) -> None:
    """1분마다 시계만 확인하고, 확인 시각이 바뀌었을 때만 API를 다시 부른다."""
    ss = st.session_state
    now = datetime.now(KST)
    check = last_check(now)

    if ss.get("check") != check:
        try:
            postings = load_postings(check.isoformat(), filters)
        except Exception as e:
            st.error(f"공고를 불러오지 못했어요. 잠시 후 다시 시도해 주세요. ({e})")
            return
        top = max((p["recrutPblntSn"] for p in postings), default=0)
        if "check" not in ss:
            # 처음 열었을 때는 오늘 공고를 '새 공고'로 보여준다
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
        ss.check = check
        ss.postings = postings
        ss.seen_sn = max(top, ss.get("seen_sn", 0))

    set_tab_title(len(ss.new))
    st.html(schedule_html(now))

    section(ss.new_title, len(ss.new))
    if ss.new:
        st.html("".join(posting_html(p) for p in ss.new))
    else:
        st.html(f'<p class="empty">{ss.new_title}는 아직 없어요.</p>')

    postings = ss.postings
    section("진행 중인 공고", len(postings))
    order = st.pills("정렬", ["최신 공고순", "마감 임박순"], default="최신 공고순",
                     label_visibility="collapsed", key="sort")
    if order == "마감 임박순":
        postings = sorted(postings, key=lambda p: (p.get("pbancEndYmd") or "99999999", -p["recrutPblntSn"]))
    else:
        postings = sorted(postings, key=lambda p: -p["recrutPblntSn"])

    shown = ss.setdefault("shown", PAGE_STEP)
    if postings:
        st.html("".join(posting_html(p) for p in postings[:shown]))
    else:
        st.html('<p class="empty">조건에 맞는 진행 중 공고가 없어요. 조건을 넓혀 보세요.</p>')
    if len(postings) > shown:
        if st.button(f"더 보기 ({len(postings) - shown}건 남음)", width="stretch"):
            ss.shown = shown + PAGE_STEP
            st.rerun(scope="fragment")


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
