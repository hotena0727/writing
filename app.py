# writing_app.py
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

# ============================================================
# ✅ Page
# ============================================================
st.set_page_config(page_title="Kanji Writing (Self-check)", layout="centered")

# ✅ 모바일에서도 "두 버튼 한 줄" 강제 + 버튼 글자 줄바꿈 방지
st.markdown(
    """
<style>
/* 두 컬럼(버튼 줄)이 모바일에서 줄바꿈(세로 스택) 되는 걸 방지 */
div[data-testid="stHorizontalBlock"]{
  flex-wrap: nowrap !important;
  gap: 0.75rem !important;
}

/* 버튼 텍스트 줄바꿈 방지 + 모바일에서 살짝 작게 */
div.stButton > button{
  white-space: nowrap !important;
}
@media (max-width: 520px){
  div.stButton > button{
    font-size: 0.98rem !important;
    padding-top: 0.85rem !important;
    padding-bottom: 0.85rem !important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# ✅ Supabase
# ============================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("st.secrets에 SUPABASE_URL / SUPABASE_ANON_KEY를 설정해 주세요.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================================================
# ✅ Utils: Korea time (Asia/Seoul fixed offset)
# ============================================================
KST = timezone(timedelta(hours=9))


def today_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def stable_seed(*parts: str) -> int:
    s = "|".join(parts)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# ============================================================
# ✅ Handwriting Canvas (원고지 격자 + 필기)
#   - ✅ 모바일에서 가로로 더 길게(160vw) + 좌우 스크롤
#   - ✅ 오른쪽/아래 끝선 잘림 방지
#   - ✅ 중요: components.html(..., scrolling=True)
# ============================================================
def handwriting_canvas(component_key: str, height: int = 320):
    html = r"""
<div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;">
  <style>
    .kw-canvas {
      width: 100%;
      height: __H__px;
      display: block;
      border-radius: 14px;
      background: rgba(255,255,255,0.02);
      touch-action: none;
    }
    /* 모바일: 가로로 길게 펼치기 */
    @media (max-width: 768px){
      .kw-canvas { width: 160vw; }
    }

    .kw-wrap{
      width: 100%;
      border: 2px solid rgba(120,120,120,0.22);
      border-radius: 18px;
      background: rgba(255,255,255,0.02);
      padding: 12px;
      box-sizing: border-box;
    }
    .kw-top{ display:flex; justify-content:space-between; align-items:center; gap:10px; }
    .kw-title{ font-weight:900; opacity:0.75; }
    .kw-clear{
      border:1px solid rgba(120,120,120,0.25);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      padding: 6px 10px;
      font-weight:900;
      cursor:pointer;
      white-space: nowrap;
    }
    /* 가로 스크롤 컨테이너 */
    .kw-scroll{
      margin-top:10px;
      width:100%;
      overflow-x:auto;
      overflow-y:hidden;
      -webkit-overflow-scrolling: touch;
      border-radius:14px;
    }
    .kw-bottom{ margin-top:10px; display:flex; justify-content:flex-end; }
    .kw-save{
      border:0;
      background: rgba(0,0,0,0.75);
      color:white;
      border-radius: 12px;
      padding: 10px 14px;
      font-weight:900;
      cursor:pointer;
      white-space: nowrap;
    }
  </style>

  <div class="kw-wrap">
    <div class="kw-top">
      <div class="kw-title">✍️ 여기 한자를 써 보세요</div>
      <button id="__KEY___clear" class="kw-clear">지우기</button>
    </div>

    <div class="kw-scroll">
      <canvas id="__KEY___canvas" class="kw-canvas"></canvas>
    </div>

    <div class="kw-bottom">
      <button id="__KEY___done" class="kw-save">필기 저장</button>
    </div>
  </div>

  <script>
    const canvas = document.getElementById("__KEY___canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const dpr = window.devicePixelRatio || 1;

    function resizeCanvasToCSS(){
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function cw(){ return canvas.width / dpr; }
    function ch(){ return canvas.height / dpr; }

    function drawGrid(){
      const w = cw();
      const h = ch();

      const cols = 20;
      const cell = w / cols;
      const rows = Math.floor(h / cell);

      ctx.save();

      ctx.clearRect(0,0,w,h);
      ctx.fillStyle = "rgba(255,255,255,0.02)";
      ctx.fillRect(0,0,w,h);

      ctx.globalAlpha = 0.22;
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(0,0,0,0.25)";

      const off = 0.5;
      ctx.beginPath();

      // ✅ 마지막 선은 w-off 안쪽으로(잘림 방지)
      for(let c=0; c<=cols; c++){
        const rawX = c * cell;
        const x = (c === cols) ? (w - off) : (rawX + off);
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
      }

      // ✅ 마지막 선은 h-off 안쪽으로(잘림 방지)
      for(let r=0; r<=rows; r++){
        const rawY = r * cell;
        const y = (r === rows) ? (h - off) : (rawY + off);
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
      }

      ctx.stroke();
      ctx.restore();

      ctx.lineWidth = 7;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "rgba(0,0,0,0.92)";
    }

    resizeCanvasToCSS();
    drawGrid();

    window.addEventListener("resize", () => {
      resizeCanvasToCSS();
      drawGrid();
    });

    let drawing = false;

    function getPos(e){
      const rect = canvas.getBoundingClientRect();
      const touch = e.touches && e.touches[0];
      const clientX = touch ? touch.clientX : e.clientX;
      const clientY = touch ? touch.clientY : e.clientY;
      return { x: clientX - rect.left, y: clientY - rect.top };
    }

    function start(e){
      e.preventDefault();
      drawing = true;
      const p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    }

    function move(e){
      if(!drawing) return;
      e.preventDefault();
      const p = getPos(e);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }

    function end(e){
      if(!drawing) return;
      e.preventDefault();
      drawing = false;
    }

    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);

    canvas.addEventListener("touchstart", start, { passive:false });
    canvas.addEventListener("touchmove", move, { passive:false });
    window.addEventListener("touchend", end, { passive:false });

    document.getElementById("__KEY___clear").addEventListener("click", () => {
      drawGrid();
    });

    document.getElementById("__KEY___done").addEventListener("click", () => {
      const png = canvas.toDataURL("image/png");
      window.parent.postMessage(
        { type:"STREAMLIT_SET_COMPONENT_VALUE", value:{ png_b64: png, ts: Date.now() } },
        "*"
      );
    });
  </script>
</div>
"""
    html = html.replace("__KEY__", component_key).replace("__H__", str(height))
    # ✅ scrolling=True : 모바일에서 내부 가로 스크롤이 실제로 동작하게
    return components.html(html, height=height + 140, scrolling=True)


# ============================================================
# ✅ Auth UI
# ============================================================
def auth_block():
    st.title("📝 Kanji Writing (Self-check)")
    st.caption("문장 속 (히라가나)를 한자로 써 보고, 채점 버튼으로 정답 확인 후 스스로 정/오를 체크합니다.")

    tab1, tab2 = st.tabs(["로그인", "회원가입"])

    with tab1:
        email = st.text_input("이메일", key="login_email")
        pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", use_container_width=True):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.session_state.session = res.session
                st.success("로그인 완료!")
                st.rerun()
            except Exception as e:
                st.error(f"로그인 실패: {e}")

    with tab2:
        email2 = st.text_input("이메일", key="signup_email")
        pw2 = st.text_input("비밀번호", type="password", key="signup_pw")
        if st.button("회원가입", use_container_width=True):
            try:
                sb.auth.sign_up({"email": email2, "password": pw2})
                st.success("회원가입 완료! 이메일 인증이 필요할 수 있습니다.")
            except Exception as e:
                st.error(f"회원가입 실패: {e}")


def require_login() -> bool:
    return "user" in st.session_state and st.session_state.user


# ============================================================
# ✅ Data fetch
# ============================================================
def fetch_sentences(bucket: str):
    res = (
        sb.table("kanji_writing_sentences")
        .select("qid,bucket,level,sentence,answer_kanji,note")
        .eq("bucket", bucket)
        .eq("is_active", True)
        .execute()
    )
    return res.data or []


def fetch_attempted_qids(user_id: str, bucket: str):
    res = (
        sb.table("kanji_writing_attempts")
        .select("qid")
        .eq("user_id", user_id)
        .eq("bucket", bucket)
        .execute()
    )
    data = res.data or []
    return {row["qid"] for row in data if row.get("qid")}


def insert_attempt(user_id, user_email, qid, bucket, level, self_grade, drawing_png_b64):
    payload = {
        "user_id": user_id,
        "user_email": user_email,
        "qid": qid,
        "bucket": bucket,
        "level": level,
        "self_grade": self_grade,
        "drawing_png_b64": drawing_png_b64,
    }
    sb.table("kanji_writing_attempts").insert(payload).execute()


# ============================================================
# ✅ Today set builder
# ============================================================
def build_today_set(user_id: str, bucket: str, n: int = 10):
    all_rows = fetch_sentences(bucket)
    if not all_rows:
        return []

    attempted = fetch_attempted_qids(user_id, bucket)
    fresh = [r for r in all_rows if r["qid"] not in attempted]
    fallback = [r for r in all_rows if r["qid"] in attempted]

    seed = stable_seed(user_id, today_kst_str(), bucket)
    rng = random.Random(seed)
    rng.shuffle(fresh)
    rng.shuffle(fallback)

    return (fresh + fallback)[:n]


# ============================================================
# ✅ Main UI after login
# ============================================================
def main_app():
    user = st.session_state.user
    user_id = str(user.id)
    user_email = user.email or ""

    st.title("📝 한자 쓰기 (자기 채점)")
    st.caption("문장 속 (히라가나)를 한자로 써 보고 → 채점 버튼으로 정답 확인 → 스스로 정/오 체크")

    top = st.columns([1, 1])
    with top[0]:
        if st.button("로그아웃", use_container_width=True):
            try:
                sb.auth.sign_out()
            except Exception:
                pass
            st.session_state.user = None
            st.session_state.session = None
            st.rerun()

    with top[1]:
        save_drawing = st.toggle("필기 이미지 저장", value=False, help="ON이면 필기 PNG(base64)를 DB에 저장합니다. (DB 용량 주의)")

    st.divider()

    bucket_label = {"beginner": "초급", "intermediate": "중급", "advanced": "상급"}

    bucket = st.segmented_control(
        "레벨 선택",
        options=["beginner", "intermediate", "advanced"],
        format_func=lambda x: bucket_label[x],
        default=st.session_state.get("bucket", "beginner"),
        key="bucket",
    )

    signature = f"{user_id}|{today_kst_str()}|{bucket}"
    if st.session_state.get("today_signature") != signature:
        st.session_state.today_signature = signature
        st.session_state.today_set = build_today_set(user_id, bucket, n=10)
        st.session_state.idx = 0
        st.session_state.revealed = False
        st.session_state.last_canvas = None

    today_set = st.session_state.get("today_set", [])
    if not today_set:
        st.warning("해당 레벨 문제풀이가 비어 있습니다. kanji_writing_sentences에 데이터를 넣어 주세요.")
        st.stop()

    idx = st.session_state.get("idx", 0)
    idx = max(0, min(idx, len(today_set)))

    if idx >= len(today_set):
        st.success("✅ 오늘의 10문장 완료!")
        if st.button("오늘 다시 처음부터 보기", use_container_width=True):
            st.session_state.idx = 0
            st.session_state.revealed = False
            st.session_state.last_canvas = None
            st.rerun()
        return

    row = today_set[idx]
    qid = row["qid"]
    sentence = row["sentence"]
    answer_kanji = row["answer_kanji"]
    level = row["level"]
    note = row.get("note") or ""

    st.markdown(f"### {bucket_label[bucket]} · {idx+1} / {len(today_set)}")
    st.progress((idx + 1) / len(today_set))

    st.markdown("#### Q.")
    st.markdown(f"**{sentence}**")

    if note:
        with st.expander("힌트/노트"):
            st.write(note)

    st.markdown("#### 필기")
    canvas_key = f"canvas_{today_kst_str()}_{bucket}_{qid}_{idx}"
    canvas_payload = handwriting_canvas(canvas_key, height=320)

    # ✅ "필기 저장" 눌렀을 때만 값이 들어옴
    if canvas_payload and isinstance(canvas_payload, dict) and canvas_payload.get("png_b64"):
        st.session_state.last_canvas = canvas_payload.get("png_b64")
        st.toast("필기 저장됨", icon="✍️")

    st.divider()

    # ============================================================
    # ✅ 채점 / 다음 문제 (모바일에서도 한 줄)
    # ============================================================
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟦 채점", use_container_width=True, key=f"btn_check_{qid}_{idx}"):
            st.session_state.revealed = True
            st.rerun()

    with c2:
        if st.button("⏭️ 다음 문제", use_container_width=True, key=f"btn_next_{qid}_{idx}"):
            st.session_state.idx = idx + 1
            st.session_state.revealed = False
            st.session_state.last_canvas = None
            st.rerun()

    # ============================================================
    # ✅ 정답 표시 + 정/오 (모바일에서도 한 줄)
    # ============================================================
    if st.session_state.get("revealed", False):
        st.markdown("### ✅ 정답")
        st.markdown(f"**{answer_kanji}**")
        st.caption("정답을 확인했으면 아래에서 스스로 정/오를 선택해 주세요.")

        g1, g2 = st.columns(2)
        with g1:
            if st.button("⭕ 정답", use_container_width=True, type="primary", key=f"btn_correct_{qid}_{idx}"):
                insert_attempt(
                    user_id=user_id,
                    user_email=user_email,
                    qid=qid,
                    bucket=bucket,
                    level=level,
                    self_grade="correct",
                    drawing_png_b64=st.session_state.last_canvas if save_drawing else None,
                )
                st.session_state.idx = idx + 1
                st.session_state.revealed = False
                st.session_state.last_canvas = None
                st.rerun()

        with g2:
            if st.button("❌ 오답", use_container_width=True, key=f"btn_wrong_{qid}_{idx}"):
                insert_attempt(
                    user_id=user_id,
                    user_email=user_email,
                    qid=qid,
                    bucket=bucket,
                    level=level,
                    self_grade="wrong",
                    drawing_png_b64=st.session_state.last_canvas if save_drawing else None,
                )
                st.session_state.idx = idx + 1
                st.session_state.revealed = False
                st.session_state.last_canvas = None
                st.rerun()


# ============================================================
# ✅ Entry
# ============================================================
if not require_login():
    auth_block()
else:
    main_app()
