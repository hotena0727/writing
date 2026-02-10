from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

# ============================================================
# Page
# ============================================================
st.set_page_config(page_title="Kanji Writing (Self-check)", layout="centered")

# ============================================================
# Supabase
# ============================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("st.secrets에 SUPABASE_URL / SUPABASE_ANON_KEY를 설정해 주세요.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================================================
# Utils
# ============================================================
KST = timezone(timedelta(hours=9))


def today_kst_str():
    return datetime.now(KST).strftime("%Y-%m-%d")


def stable_seed(*parts: str) -> int:
    s = "|".join(parts)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# ============================================================
# Custom Components
# ============================================================
_dual_buttons = components.declare_component(
    "dual_buttons",
    path=None,
)

_handwriting_canvas = components.declare_component(
    "handwriting_canvas",
    path=None,
)


def dual_buttons(key, left_label, right_label):
    return _dual_buttons(
        key=key,
        left_label=left_label,
        right_label=right_label,
        default=None,
    )


def handwriting_canvas(key, height=320):
    return _handwriting_canvas(
        key=key,
        height=height,
        default=None,
    )


# ============================================================
# Data
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
    return {r["qid"] for r in (res.data or [])}


def insert_attempt(**payload):
    sb.table("kanji_writing_attempts").insert(payload).execute()


# ============================================================
# Today set
# ============================================================
def build_today_set(user_id: str, bucket: str, n=10):
    all_rows = fetch_sentences(bucket)
    if not all_rows:
        return []

    attempted = fetch_attempted_qids(user_id, bucket)
    fresh = [r for r in all_rows if r["qid"] not in attempted]
    fallback = [r for r in all_rows if r["qid"] in attempted]

    rng = random.Random(stable_seed(user_id, today_kst_str(), bucket))
    rng.shuffle(fresh)
    rng.shuffle(fallback)

    return (fresh + fallback)[:n]


# ============================================================
# Auth
# ============================================================
def require_login():
    return "user" in st.session_state and st.session_state.user


# ============================================================
# Main App
# ============================================================
def main_app():
    user = st.session_state.user
    user_id = str(user.id)
    email = user.email or ""

    bucket_label = {"beginner": "초급", "intermediate": "중급", "advanced": "상급"}

    bucket = st.segmented_control(
        "레벨 선택",
        options=list(bucket_label.keys()),
        format_func=lambda x: bucket_label[x],
        key="bucket",
        default=st.session_state.get("bucket", "beginner"),
    )

    sig = f"{user_id}|{today_kst_str()}|{bucket}"
    if st.session_state.get("sig") != sig:
        st.session_state.sig = sig
        st.session_state.today = build_today_set(user_id, bucket)
        st.session_state.idx = 0
        st.session_state.revealed = False
        st.session_state.canvas = None

    today = st.session_state.today
    idx = st.session_state.idx

    if idx >= len(today):
        st.success("오늘의 학습 완료 🎉")
        return

    row = today[idx]

    st.markdown(f"### {bucket_label[bucket]} · {idx+1} / {len(today)}")
    st.markdown(f"**{row['sentence']}**")

    canvas = handwriting_canvas(
        key=f"canvas_{row['qid']}_{idx}",
        height=320,
    )
    if canvas:
        st.session_state.canvas = canvas

    action = dual_buttons(
        key=f"act_{row['qid']}_{idx}",
        left_label="🟦 채점",
        right_label="⏭️ 다음 문제",
    )

    if action == "left":
        st.session_state.revealed = True
        st.rerun()

    if action == "right":
        st.session_state.idx += 1
        st.session_state.revealed = False
        st.rerun()

    if st.session_state.revealed:
        st.markdown(f"### ✅ 정답: **{row['answer_kanji']}**")

        grade = dual_buttons(
            key=f"grade_{row['qid']}_{idx}",
            left_label="⭕ 정답",
            right_label="❌ 오답",
        )

        if grade in ("left", "right"):
            insert_attempt(
                user_id=user_id,
                user_email=email,
                qid=row["qid"],
                bucket=bucket,
                level=row["level"],
                self_grade="correct" if grade == "left" else "wrong",
                drawing_png_b64=st.session_state.canvas,
            )
            st.session_state.idx += 1
            st.session_state.revealed = False
            st.session_state.canvas = None
            st.rerun()


# ============================================================
# Entry
# ============================================================
if not require_login():
    st.warning("로그인이 필요합니다.")
else:
    main_app()
