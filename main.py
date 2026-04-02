from __future__ import annotations

from typing import Any

import streamlit as st

from education_agent import build_initial_state, graph

st.set_page_config(
    page_title="Education Agent",
    page_icon="🎓",
    layout="wide",
)

EXAMPLE_PROMPTS = [
    {
        "topic": "Python 함수",
        "goal": "함수를 직접 정의하고 호출할 수 있다",
        "learner_level": "beginner",
        "available_minutes": 30,
    },
    {
        "topic": "자료구조",
        "goal": "문제에 맞는 자료구조를 비교해서 선택할 수 있다",
        "learner_level": "intermediate",
        "available_minutes": 55,
    },
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(255, 210, 157, 0.25), transparent 28%),
                linear-gradient(180deg, #fffaf2 0%, #f5efe4 100%);
        }
        .hero {
            padding: 1.5rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #17324d 0%, #234a6c 55%, #34688f 100%);
            color: #f8fafc;
            box-shadow: 0 18px 40px rgba(23, 50, 77, 0.18);
            margin-bottom: 1rem;
        }
        .hero h1 {
            margin: 0 0 0.5rem 0;
            font-size: 2rem;
        }
        .hero p {
            margin: 0;
            line-height: 1.6;
            font-size: 1rem;
            color: rgba(248, 250, 252, 0.92);
        }
        .panel {
            padding: 1rem 1.1rem;
            background: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(23, 50, 77, 0.08);
            border-radius: 18px;
            margin-bottom: 1rem;
            backdrop-filter: blur(8px);
        }
        .panel-title {
            font-size: 0.82rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #4a5d70;
            margin-bottom: 0.4rem;
            font-weight: 700;
        }
        .panel-value {
            font-size: 1.02rem;
            color: #12263a;
            line-height: 1.6;
        }
        .quiz-card {
            padding: 0.9rem 1rem;
            border-radius: 16px;
            background: #ffffff;
            border: 1px solid rgba(35, 74, 108, 0.1);
            margin-bottom: 0.75rem;
        }
        .quiz-label {
            font-size: 0.78rem;
            color: #5f7183;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "result" not in st.session_state:
        st.session_state["result"] = None

    if "selected_example" not in st.session_state:
        st.session_state["selected_example"] = EXAMPLE_PROMPTS[0]


def apply_example(index: int) -> None:
    st.session_state["selected_example"] = EXAMPLE_PROMPTS[index]


def validate_inputs(topic: str, goal: str, available_minutes: int) -> list[str]:
    errors: list[str] = []

    if not topic.strip():
        errors.append("학습 주제를 입력해 주세요.")
    if not goal.strip():
        errors.append("학습 목표를 입력해 주세요.")
    if available_minutes < 10:
        errors.append("학습 시간은 최소 10분 이상으로 설정해 주세요.")

    return errors


def run_education_agent(
    *,
    topic: str,
    goal: str,
    learner_level: str,
    available_minutes: int,
) -> dict[str, Any]:
    state = build_initial_state(
        topic=topic.strip(),
        goal=goal.strip(),
        learner_level=learner_level,
        available_minutes=available_minutes,
    )
    return graph.invoke(state)


def render_header() -> None:
    st.markdown(
        """
        <section class="hero">
            <h1>Education Agent</h1>
            <p>
                학습 주제, 목표, 수준, 시간을 입력하면 EduPath Coach가 맞춤 학습 계획,
                요약 레슨, 확인 퀴즈, 다음 행동 가이드를 한 번에 구성합니다.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    st.sidebar.header("빠른 시작")
    st.sidebar.write("예시 입력을 불러와 바로 실행할 수 있습니다.")

    if st.sidebar.button("예시 1 불러오기", use_container_width=True):
        apply_example(0)
    if st.sidebar.button("예시 2 불러오기", use_container_width=True):
        apply_example(1)

    st.sidebar.markdown("---")
    st.sidebar.info(
        "입력 후 `학습 경로 생성하기`를 누르면 로컬 레퍼런스를 참고해 학습 경로를 만듭니다."
    )


def render_form() -> tuple[str, str, str, int, bool]:
    example = st.session_state["selected_example"]

    with st.form("education-agent-form"):
        st.subheader("학습 정보 입력")
        topic = st.text_input(
            "학습 주제",
            value=example["topic"],
            placeholder="예: Python 함수",
            help="오늘 학습할 핵심 주제를 입력하세요.",
        )
        goal = st.text_area(
            "학습 목표",
            value=example["goal"],
            height=100,
            placeholder="예: 함수를 직접 정의하고 호출할 수 있다",
            help="이번 학습이 끝났을 때 할 수 있어야 하는 일을 적어 주세요.",
        )
        learner_level = st.selectbox(
            "학습 수준",
            options=["beginner", "intermediate", "advanced"],
            index=["beginner", "intermediate", "advanced"].index(example["learner_level"]),
            help="현재 본인의 이해 수준에 가장 가까운 단계를 선택하세요.",
        )
        available_minutes = st.slider(
            "학습 가능 시간(분)",
            min_value=10,
            max_value=120,
            value=example["available_minutes"],
            step=5,
            help="40분 미만이면 빠른 학습 경로, 이상이면 집중 학습 경로가 제안됩니다.",
        )
        submitted = st.form_submit_button("학습 경로 생성하기", use_container_width=True)

    return topic, goal, learner_level, available_minutes, submitted


def render_result(result: dict[str, Any]) -> None:
    lesson_mode_label = "빠른 학습" if result["lesson_mode"] == "quick" else "집중 학습"

    st.success("학습 경로를 생성했습니다. 아래 내용을 따라 바로 학습을 시작할 수 있습니다.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">추천 학습 경로</div>
                <div class="panel-value">{lesson_mode_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">참고 노트</div>
                <div class="panel-value">{result["reference_note"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("학습 공백 진단")
    for gap in result["knowledge_gaps"]:
        st.write(f"- {gap}")

    st.subheader("맞춤 학습 계획")
    for step in result["study_plan"]:
        st.write(f"- {step}")

    st.subheader("미니 레슨")
    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-value">{result["lesson_summary"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("확인 퀴즈")
    for index, quiz in enumerate(result["quiz"], start=1):
        st.markdown(
            f"""
            <div class="quiz-card">
                <div class="quiz-label">문항 {index} · {quiz["type"]}</div>
                <div>{quiz["question"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("마무리 피드백")
    st.info(result["final_feedback"])


def main() -> None:
    inject_styles()
    init_state()
    render_sidebar()
    render_header()

    st.caption("오류가 발생하면 입력 조건을 다시 확인하고 새로 실행해 주세요.")

    topic, goal, learner_level, available_minutes, submitted = render_form()

    if submitted:
        errors = validate_inputs(topic, goal, available_minutes)
        if errors:
            for error in errors:
                st.error(error)
        else:
            with st.spinner("Education Agent가 맞춤 학습 경로를 만들고 있습니다..."):
                try:
                    st.session_state["result"] = run_education_agent(
                        topic=topic,
                        goal=goal,
                        learner_level=learner_level,
                        available_minutes=available_minutes,
                    )
                except FileNotFoundError:
                    st.session_state["result"] = None
                    st.error(
                        "학습 참고 자료 파일을 찾지 못했습니다. `education_reference_notes.json` 파일을 확인해 주세요."
                    )
                except Exception as exc:
                    st.session_state["result"] = None
                    st.error(
                        "Education Agent 실행 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
                    )
                    st.exception(exc)

    if st.session_state["result"]:
        render_result(st.session_state["result"])
    else:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">사용 안내</div>
                <div class="panel-value">
                    왼쪽 사이드바 예시를 불러오거나 직접 학습 정보를 입력한 뒤,
                    <strong>학습 경로 생성하기</strong> 버튼을 눌러 주세요.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
