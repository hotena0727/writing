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

# ============================================================
# ✅ Mobile UI CSS
#   - "채점 / 다음 문제"를 모바일에서도 무조건 한 줄 2개로 고정
#   - (필요하면 "정답 / 오답"도 같은 방식으로 한 줄 고정 가능)
# ============================================================
st.markdown(
    """
<style>
/* ✅ 앵커(#kw_row_anchor) 바로 다음 "가로 columns 블록"만: 1줄 고정 */
#kw_row_anchor + div[data-testid="stHorizontalBlock"]{
  flex-wrap: nowrap !important;
  gap: 0.45rem !important;
}

/* ✅ 각 컬럼이 반반 차지 + 줄바꿈 방지 */
#kw_row_anchor + div[data-testid="stHorizontalBlock"] > div{
  flex: 1 1 0 !important;
  min-width: 0 !important;   /* 핵심: 모바일에서 줄바꿈/밀림 방지 */
}

/* ✅ 버튼도 폭 100% + 글자 줄바꿈 방지 */
#kw_row_anchor + div[data-testid="stHorizontalBlock"] button{
  width: 100% !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  font-size: clamp(12px, 3.2vw, 16px) !important;
  padding: clamp(10px, 2.8vw, 14px) clamp(8px, 2.4vw, 12px) !important;
}

@media (max-width: 360px){
  #kw_row_anchor + div[data-testid="stHorizontalBlock"]{
    gap: 0.30rem !important;
  }
  #kw_row_anchor + div[data-testid="stHorizontalBlock"] button{
    font-size: 12px !important;
    padding: 10px 8px !important;
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


def ensure_sb_session():
    """Streamlit rerun 시 RLS 통과를 위해 supabase client에 세션 주입"""
    sess = st.session_state.get("session")
    if sess:
        try:
            sb.auth.set_session(sess.access_token, sess.refresh_token)
        except Exception:
            # 세션이 만료/깨졌을 수 있으니 조용히 패스
            pass


# ============================================================
# ✅ Handwriting Canvas (원고지 격자 + 필기)
#   - "필기 저장" 버튼 누르면 base64 PNG 반환
#   - 모바일에서도 가로로 길게(좌우 스크롤)
# ============================================================
def handwriting_canvas(component_key: str, height: int = 320):
    html = r"""
<div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;">
  <div style="
    width: 100%;
    border: 2px solid rgba(120,120,120,0.22);
    border-radius: 18px;
    background: rgba(255,255,255,0.02);
    padding: 12px;
    box-sizing: border-box;
  ">
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <div style="font-weight:900; opacity:0.75;">✍️ 여기 한자를 써 보세요</div>
      <button id="__KEY___clear" style="
        border:1px solid rgba(120,120,120,0.25);
        background: rgba(255,255,255,0.03);
        border-radius: 999px;
        padding: 6px 10px;
        font-weight:900;
        cursor:pointer;
      ">지우기</button>
    </div>

    <!-- ✅ 모바일에서도 '가로로 길게' 보이게: 가로 스크롤 랩 -->
    <div style="margin-top:10px;">
      <div id="__KEY___scrollwrap" style="
        width: 100%;
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        border-radius: 14px;
      ">
        <div style="width: __CW__px; max-width: none;">
          <canvas id="__KEY___canvas" style="
            width: __CW__px;
            height: __H__px;
            border-radius: 14px;
            background: rgba(255,255,255,0.02);
            display:block;
            touch-action: none;
          "></canvas>
        </div>
      </div>
    </div>

    <div style="margin-top:10px; display:flex; justify-content:flex-end;">
      <button id="__KEY___done" style="
        border:0;
        background: rgba(0,0,0,0.75);
        color:white;
        border-radius: 12px;
        padding: 10px 14px;
        font-weight:900;
        cursor:pointer;
      ">필기 저장</button>
    </div>
  </div>

  <script>
    const canvas = document.getElementById("__KEY___canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth;
    const cssHeight = canvas.clientHeight;

    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    function cw() { return canvas.width / dpr; }
    function ch() { return canvas.height / dpr; }

    function drawGrid() {
      const w = cw();
      const h = ch();

      const cols = 20;
      const cell = w / cols;
      const rows = Math.floor(h / cell);

      ctx.save();
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "rgba(255,255,255,0.02)";
      ctx.fillRect(0, 0, w, h);

      ctx.globalAlpha = 0.22;
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(0,0,0,0.25)";
      const off = 0.5;

      ctx.beginPath();
      for (let c = 0; c <= cols; c++) {
        const x = c * cell;
        ctx.moveTo(x + off, 0);
        ctx.lineTo(x + off, h);
      }
      for (let r = 0; r <= rows; r++) {
        const y = r * cell;
        ctx.moveTo(0, y + off);
        ctx.lineTo(w, y + off);
      }
      ctx.stroke();
      ctx.restore();
    }

    drawGrid();

    ctx.lineWidth = 7;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "rgba(0,0,0,0.92)";

    let drawing = false;

    function getPos(e) {
      const rect = canvas.getBoundingClientRect();
      const touch = e.touches && e.touches[0];
      const clientX = touch ? touch.clientX : e.clientX;
      const clientY = touch ? touch.clientY : e.clientY;
      return { x: clientX - rect.left, y: clientY - rect.top };
    }

    function start(e) {
      e.preventDefault();
      drawing = true;
      const p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    }

    function move(e) {
      if (!drawing) return;
      e.preventDefault();
      const p = getPos(e);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }

    function end(e) {
      if (!drawing) return;
      e.preventDefault();
      d



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

        if st.button("로그인", use_container_width=True, key="btn_login"):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.session_state.session = res.session

                # ✅ RLS 통과용: 이후 요청은 이 토큰으로
                sb.auth.set_session(res.session.access_token, res.session.refresh_token)

                st.success("로그인 완료!")
                st.rerun()
            except Exception as e:
                st.error(f"로그인 실패: {e}")

    with tab2:
        email2 = st.text_input("이메일", key="signup_email")
        pw2 = st.text_input("비밀번호", type="password", key="signup_pw")
        if st.button("회원가입", use_container_width=True, key="btn_signup"):
            try:
                sb.auth.sign_up({"email": email2, "password": pw2})
                st.success("회원가입 완료! 이메일 인증이 필요할 수 있습니다.")
            except Exception as e:
                st.error(f"회원가입 실패: {e}")


def require_login() -> bool:
    return bool(st.session_state.get("user"))


# ============================================================
# ✅ Data fetch
# ============================================================
def fetch_sentences(bucket: str):
    ensure_sb_session()
    res = (
        sb.table("kanji_writing_sentences")
        .select("qid,bucket,level,sentence,target_kana,answer_kanji,note")
        .eq("bucket", bucket)
        .eq("is_active", True)
        .execute()
    )
    return res.data or []


def fetch_attempted_qids(user_id: str, bucket: str):
    ensure_sb_session()
    res = (
        sb.table("kanji_writing_attempts")
        .select("qid")
        .eq("user_id", user_id)
        .eq("bucket", bucket)
        .execute()
    )
    data = res.data or []
    return {row["qid"] for row in data if row.get("qid")}


def insert_attempt(
    user_id: str,
    user_email: str,
    qid: str,
    bucket: str,
    level: str,
    self_grade: str,
    drawing_png_b64: str | None,
):
    ensure_sb_session()
    payload = {
        "user_id": user_id,
        "user_email": user_email,
        "qid": qid,
        "bucket": bucket,
        "level": level,
        "self_grade": self_grade,
    }
    if drawing_png_b64:
        payload["drawing_png_b64"] = drawing_png_b64

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
    ensure_sb_session()

    user = st.session_state.user
    user_id = str(user.id)
    user_email = user.email or ""

    st.title("📝 한자 쓰기 (자기 채점)")
    st.caption("문장 속 (히라가나)를 한자로 써 보고 → 채점 버튼으로 정답 확인 → 스스로 정/오 체크")

    top = st.columns([1, 1])
    with top[0]:
        if st.button("로그아웃", use_container_width=True, key="btn_logout"):
            try:
                sb.auth.sign_out()
            except Exception:
                pass
            st.session_state.user = None
            st.session_state.session = None
            st.rerun()

    with top[1]:
        save_drawing = st.toggle(
            "필기 이미지 저장", value=False, help="ON이면 필기 PNG(base64)를 DB에 저장합니다. (DB 용량 주의)"
        )

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
        if st.button("오늘 다시 처음부터 보기", use_container_width=True, key="btn_restart"):
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

    if canvas_payload and isinstance(canvas_payload, dict) and canvas_payload.get("png_b64"):
        st.session_state.last_canvas = canvas_payload.get("png_b64")
        st.toast("필기 저장됨", icon="✍️")

    st.divider()

    # ✅ (A) 먼저: URL 쿼리파라미터로 들어온 액션 처리
    qp = st.query_params
    kw_action = qp.get("kw_action", None)
    kw_key = qp.get("kw_key", None)

    # ✅ 현재 문제용 key (다른 문제에서 눌린 action이 섞이지 않게)
    btn_key = f"kw_btns_{today_kst_str()}_{bucket}_{qid}_{idx}"

    if kw_action and kw_key == btn_key:
        # 처리 후 쿼리파라미터 제거(무한 반복 방지)
        st.query_params.clear()
        if kw_action == "check":
            st.session_state.revealed = True
            st.rerun()
        elif kw_action == "next":
            st.session_state.idx = idx + 1
            st.session_state.revealed = False
            st.session_state.last_canvas = None
            st.rerun()

    # ✅ (B) 버튼 렌더링: 모바일에서도 무조건 1줄 2개
    two_action_buttons(btn_key)

    # ✅ 정답 공개 이후: 스스로 정/오 체크
    if st.session_state.get("revealed", False):
        st.markdown("### ✅ 정답")
        st.markdown(f"**{answer_kanji}**")
        st.caption("정답을 확인했으면 아래에서 스스로 정/오를 선택해 주세요.")

        g1, g2 = st.columns(2)
        with g1:
            if st.button("⭕ 정답", use_container_width=True, type="primary", key=f"btn_correct_{qid}_{idx}"):
                try:
                    insert_attempt(
                        user_id=user_id,
                        user_email=user_email,
                        qid=qid,
                        bucket=bucket,
                        level=level,
                        self_grade="correct",
                        drawing_png_b64=st.session_state.last_canvas if save_drawing else None,
                    )
                except Exception as e:
                    st.error(f"저장 실패: {e}")
                    st.stop()

                st.session_state.idx = idx + 1
                st.session_state.revealed = False
                st.session_state.last_canvas = None
                st.rerun()

        with g2:
            if st.button("❌ 오답", use_container_width=True, key=f"btn_wrong_{qid}_{idx}"):
                try:
                    insert_attempt(
                        user_id=user_id,
                        user_email=user_email,
                        qid=qid,
                        bucket=bucket,
                        level=level,
                        self_grade="wrong",
                        drawing_png_b64=st.session_state.last_canvas if save_drawing else None,
                    )
                except Exception as e:
                    st.error(f"저장 실패: {e}")
                    st.stop()

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
