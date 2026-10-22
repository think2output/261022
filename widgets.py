"""브라우저와 주고받는 작은 컴포넌트들 (st.components.v2, iframe 없이 페이지에서 실행).

- browser_store: localStorage 읽기/쓰기 (관심, 패스, 마지막으로 본 공고번호)
- job_list: 공고 목록. 행을 누르면 상세, ☆를 누르면 관심
- swipe_card: 넘겨보기 카드. 끌어서 넘기기, 버튼, 키보드 ←/→
- notifier: 브라우저 알림 권한 받기와 알림 띄우기
- korea_map: 시도 지도. 지역을 누르면 그 지역 코드를 돌려준다

HTML은 모두 app.py 에서 html.escape 로 만든 문자열만 넘긴다.
"""
import streamlit as st

STORE_KEY = "public-job-alert:v1"

_store = st.components.v2.component(
    "browser_store",
    js=f"""
export default function ({{ data, setStateValue }}) {{
  const KEY = "{STORE_KEY}";
  try {{
    if (data && typeof data.write === "string") {{
      localStorage.setItem(KEY, data.write);
    }} else {{
      setStateValue("saved", localStorage.getItem(KEY) || "");
    }}
  }} catch (e) {{
    if (!(data && typeof data.write === "string")) setStateValue("saved", "");
  }}
}}
""",
)


def browser_store(write: str | None, key: str = "browser_store") -> str | None:
    """write 가 None 이면 저장된 값을 읽어 돌려주고(첫 실행에는 아직 None), 문자열이면 저장한다."""
    res = _store(data={"write": write}, key=key, on_saved_change=lambda: None)
    return getattr(res, "saved", None)


_job_list = st.components.v2.component(
    "job_list",
    isolate_styles=False,
    js="""
export default function ({ data, parentElement, setTriggerValue }) {
  let root = parentElement.querySelector(":scope > .job-list");
  if (!root) {
    root = document.createElement("div");
    root.className = "job-list";
    parentElement.appendChild(root);
  }
  root.innerHTML = data.html;
  const fire = (type, sn) => setTriggerValue("action", { type, sn: Number(sn), at: Date.now() });
  root.onclick = (e) => {
    const star = e.target.closest("[data-star]");
    if (star) { e.preventDefault(); e.stopPropagation(); fire("star", star.dataset.star); return; }
    if (e.target.closest("a")) return;
    const row = e.target.closest("[data-open]");
    if (row) fire("open", row.dataset.open);
  };
  root.onkeydown = (e) => {
    const row = e.target.closest("[data-open]");
    if (row && e.key === "Enter" && !e.target.closest("[data-star]")) fire("open", row.dataset.open);
  };
}
""",
)


def job_list(rows_html: str, key: str) -> dict | None:
    """{"type": "open"|"star", "sn": int} 또는 None."""
    res = _job_list(data={"html": rows_html}, key=key, on_action_change=lambda: None)
    return getattr(res, "action", None)


_swipe = st.components.v2.component(
    "swipe_card",
    isolate_styles=False,
    js="""
export default function ({ data, parentElement, setTriggerValue }) {
  let root = parentElement.querySelector(":scope > .swipe");
  if (!root) {
    root = document.createElement("div");
    root.className = "swipe";
    parentElement.appendChild(root);
  }
  root.innerHTML = data.html;
  const card = root.querySelector(".swipe-card");
  const sn = Number(data.sn);
  let done = false;
  const decide = (type) => {
    if (done) return;
    if (type === "open") { setTriggerValue("action", { type, sn, at: Date.now() }); return; }
    done = true;
    const dir = type === "star" ? 1 : -1;
    card.style.transition = "transform .28s ease, opacity .28s ease";
    card.style.transform = `translateX(${dir * 420}px) rotate(${dir * 14}deg)`;
    card.style.opacity = "0";
    setTimeout(() => setTriggerValue("action", { type, sn, at: Date.now() }), 220);
  };

  root.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => decide(b.dataset.act)));

  // 끌어서 넘기기: 오른쪽 = 관심, 왼쪽 = 패스
  let startX = null, dx = 0;
  card.onpointerdown = (e) => {
    if (e.target.closest("button, a")) return;
    startX = e.clientX; dx = 0;
    card.setPointerCapture(e.pointerId);
    card.style.transition = "none";
  };
  card.onpointermove = (e) => {
    if (startX === null) return;
    dx = e.clientX - startX;
    card.style.transform = `translateX(${dx}px) rotate(${dx / 24}deg)`;
    card.dataset.hint = dx > 60 ? "star" : dx < -60 ? "pass" : "";
  };
  card.onpointerup = () => {
    if (startX === null) return;
    startX = null;
    if (dx > 110) return decide("star");
    if (dx < -110) return decide("pass");
    card.style.transition = "transform .2s ease";
    card.style.transform = "";
    card.dataset.hint = "";
    if (Math.abs(dx) < 5) decide("open");
  };

  // 키보드: ← 패스, → 관심, Enter 자세히
  if (parentElement.__swipeKeys) document.removeEventListener("keydown", parentElement.__swipeKeys);
  parentElement.__swipeKeys = (e) => {
    if (e.target.closest && e.target.closest("input, textarea")) return;
    if (!document.body.contains(card)) return;
    if (e.key === "ArrowLeft") decide("pass");
    else if (e.key === "ArrowRight") decide("star");
    else if (e.key === "Enter") decide("open");
  };
  document.addEventListener("keydown", parentElement.__swipeKeys);
  return () => document.removeEventListener("keydown", parentElement.__swipeKeys);
}
""",
)


def swipe_card(card_html: str, sn: int, key: str = "swipe") -> dict | None:
    """{"type": "star"|"pass"|"open", "sn": int} 또는 None."""
    res = _swipe(data={"html": card_html, "sn": sn}, key=key, on_action_change=lambda: None)
    return getattr(res, "action", None)


_notifier = st.components.v2.component(
    "notifier",
    isolate_styles=False,
    js="""
export default function ({ data, parentElement }) {
  // Streamlit Cloud 는 앱을 같은 주소의 프레임 안에서 띄우므로, 최상위 창의 Notification 을 먼저 쓰고 안 되면 현재 창 것을 쓴다
  const candidates = [];
  try { if (window.top.Notification) candidates.push(window.top.Notification); } catch (e) {}
  if (window.Notification && !candidates.includes(window.Notification)) candidates.push(window.Notification);
  const N = candidates[0];

  let root = parentElement.querySelector(":scope > .notif");
  if (!root) {
    root = document.createElement("div");
    root.className = "notif";
    parentElement.appendChild(root);
  }

  // 알림을 띄우고, 실패하면 이유를 문자열로 돌려준다
  const show = (title, body, tag) => {
    let lastError = null;
    for (const C of candidates) {
      try {
        const note = new C(title, { body, tag });
        note.onclick = () => { try { window.top.focus(); } catch (e) { window.focus(); } note.close(); };
        return null;
      } catch (e) { lastError = e; }
    }
    if (lastError && /constructor/i.test(String(lastError))) {
      return "휴대폰 브라우저는 이 방식의 알림을 지원하지 않아요. PC 크롬에서 확인해 주세요.";
    }
    return "알림을 띄우지 못했어요. (" + (lastError ? lastError.message || lastError : "알 수 없는 오류") + ")";
  };

  const render = (message) => {
    const extra = message ? `<span class="notif-msg err">${message}</span>` : "";
    if (!N) { root.innerHTML = '<span class="notif-msg">이 브라우저는 알림을 지원하지 않아요.</span>'; return; }
    if (N.permission === "granted") {
      root.innerHTML = '<span class="notif-msg on">브라우저 알림이 켜져 있어요.</span>'
        + '<button type="button" class="notif-btn notif-test">테스트 알림 보내기</button>' + extra;
      root.querySelector("button").onclick = () => {
        const err = show("테스트 알림이에요", "9시, 13시, 18시에 새 공고가 있으면 이렇게 알려드려요.", "test-" + Date.now());
        render(err || "알림을 보냈어요. 화면 구석에 안 보이면 윈도우 알림 설정에서 Chrome 알림이 켜져 있는지 확인해 주세요.");
      };
    } else if (N.permission === "denied") {
      root.innerHTML = '<span class="notif-msg">알림이 차단되어 있어요. 주소창 왼쪽 아이콘을 눌러 알림을 허용한 뒤 새로고침해 주세요.</span>';
    } else {
      root.innerHTML = '<button type="button" class="notif-btn">브라우저 알림 받기</button>' + extra;
      root.querySelector("button").onclick = async () => {
        try { await N.requestPermission(); } catch (e) {}
        if (N.permission === "granted") {
          render(show("알림이 켜졌어요", "9시, 13시, 18시에 새 공고가 있으면 알려드릴게요.", "welcome"));
        } else {
          render(N.permission === "default" ? "권한 창이 닫혔어요. 다시 눌러 허용해 주세요." : null);
        }
      };
    }
  };
  render();

  const n = data && data.notify;
  if (n && N && N.permission === "granted") {
    const KEY = "public-job-alert:notified";
    let last = null;
    try { last = localStorage.getItem(KEY); } catch (e) {}
    if (last !== n.id) {
      try { localStorage.setItem(KEY, n.id); } catch (e) {}
      const err = show(n.title, n.body, n.id);
      if (err) render(err);
    }
  }
}
""",
)


def notifier(notify: dict | None, key: str = "notifier") -> None:
    """notify = {"id", "title", "body"}. 같은 id 는 한 번만 띄운다."""
    _notifier(data={"notify": notify}, key=key)


_korea_map = st.components.v2.component(
    "korea_map",
    isolate_styles=False,
    js="""
export default function ({ data, parentElement, setTriggerValue }) {
  let root = parentElement.querySelector(":scope > .kmap");
  if (!root) {
    root = document.createElement("div");
    root.className = "kmap";
    parentElement.appendChild(root);
  }
  root.innerHTML = data.svg;
  root.querySelectorAll("[data-rgn]").forEach((el) => {
    el.onclick = () => setTriggerValue("region", { code: el.dataset.rgn, at: Date.now() });
  });
}
""",
)


def korea_map(svg: str, key: str = "korea_map") -> dict | None:
    """{"code": "R3010"} 또는 None."""
    res = _korea_map(data={"svg": svg}, key=key, on_region_change=lambda: None)
    return getattr(res, "region", None)
