import json
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

REFERENCE_PATH = Path(__file__).with_name("education_reference_notes.json")


class QuizItem(TypedDict):
    question: str
    type: str


class LearningState(TypedDict):
    topic: str
    goal: str
    learner_level: str
    available_minutes: int
    knowledge_gaps: list[str]
    study_plan: list[str]
    reference_note: str
    lesson_mode: str
    lesson_summary: str
    quiz: list[QuizItem]
    final_feedback: str


def _load_reference_notes() -> dict[str, str]:
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


@tool
def search_learning_reference(topic: str) -> str:
    """Search local learning notes and return a short reference for the topic."""
    notes = _load_reference_notes()
    normalized = topic.strip().lower()

    for key, note in notes.items():
        if key == "default":
            continue
        lowered = key.lower()
        if lowered in normalized or normalized in lowered:
            return note

    return notes["default"]


def diagnose_learner(state: LearningState) -> LearningState:
    topic = state["topic"]
    level = state["learner_level"].lower()
    minutes = state["available_minutes"]

    if "beginner" in level or "초급" in level:
        gaps = [
            f"{topic}의 핵심 용어 이해",
            f"{topic}의 기본 사용 패턴 익히기",
            "짧은 예제를 보고 직접 설명하는 연습",
        ]
    else:
        gaps = [
            f"{topic}를 실제 문제에 적용하는 연습",
            "정답은 맞지만 설명이 약한 부분 보완",
            "실수한 이유를 복기하고 일반화하는 습관",
        ]

    practice_minutes = max(minutes - 15, 10)
    plan = [
        f"5분: {topic}의 핵심 개념 3개 빠르게 훑기",
        f"{practice_minutes}분: 예제 2개를 보며 개념을 자신의 말로 설명하기",
        "10분: 퀴즈 3문항을 풀고 틀린 이유를 한 줄로 정리하기",
    ]

    return {
        **state,
        "knowledge_gaps": gaps,
        "study_plan": plan,
    }


def collect_reference_material(state: LearningState) -> LearningState:
    reference_note = search_learning_reference.invoke({"topic": state["topic"]})
    lesson_mode: Literal["quick", "deep"] = (
        "quick" if state["available_minutes"] < 40 else "deep"
    )

    return {
        **state,
        "reference_note": reference_note,
        "lesson_mode": lesson_mode,
    }


def route_lesson_mode(state: LearningState) -> Literal["create_quick_lesson", "create_deep_lesson"]:
    if state["lesson_mode"] == "quick":
        return "create_quick_lesson"
    return "create_deep_lesson"


def create_quick_lesson(state: LearningState) -> LearningState:
    topic = state["topic"]
    lesson = (
        f"빠른 학습 모드입니다. 오늘은 {topic}의 정의와 대표 예시 1개만 확실히 잡습니다. "
        f"참고 노트: {state['reference_note']} "
        "정의를 한 문장으로 말하고, 어디에 쓰는지 한 가지 상황만 설명하면 오늘 목표로 충분합니다."
    )
    return {
        **state,
        "lesson_summary": lesson,
    }


def create_deep_lesson(state: LearningState) -> LearningState:
    topic = state["topic"]
    goal = state["goal"]
    lesson = (
        f"집중 학습 모드입니다. 주제는 {topic}, 목표는 '{goal}'입니다. "
        f"참고 노트: {state['reference_note']} "
        f"먼저 {topic}의 정의를 설명하고, 다음으로 대표 예시 2개를 비교하며 언제 써야 하는지 구분합니다. "
        "마지막에는 헷갈리기 쉬운 실수를 한 줄로 요약해 개념을 고정합니다."
    )
    return {
        **state,
        "lesson_summary": lesson,
    }


def build_quiz(state: LearningState) -> LearningState:
    topic = state["topic"]
    quiz = [
        {
            "question": f"{topic}의 핵심 개념을 한 문장으로 설명해 보세요.",
            "type": "short_answer",
        },
        {
            "question": f"{topic}가 실제로 쓰이는 상황을 한 가지 적어 보세요.",
            "type": "application",
        },
        {
            "question": f"오늘 참고 노트에서 가장 중요한 문장을 {state['reference_note'][:35]}... 기준으로 다시 풀어 써 보세요.",
            "type": "reflection",
        },
    ]

    return {
        **state,
        "quiz": quiz,
    }


def wrap_up(state: LearningState) -> LearningState:
    mode_label = "빠른 학습" if state["lesson_mode"] == "quick" else "집중 학습"
    feedback = (
        f"{mode_label} 경로를 선택했습니다. 다음 행동: {state['study_plan'][0]} 후 "
        f"퀴즈 3문항을 풀고 '{state['knowledge_gaps'][0]}'을 다시 점검하세요."
    )

    return {
        **state,
        "final_feedback": feedback,
    }


def build_initial_state(
    *,
    topic: str,
    goal: str,
    learner_level: str,
    available_minutes: int,
) -> LearningState:
    return {
        "topic": topic,
        "goal": goal,
        "learner_level": learner_level,
        "available_minutes": available_minutes,
        "knowledge_gaps": [],
        "study_plan": [],
        "reference_note": "",
        "lesson_mode": "",
        "lesson_summary": "",
        "quiz": [],
        "final_feedback": "",
    }


def build_graph():
    builder = StateGraph(LearningState)

    builder.add_node("diagnose_learner", diagnose_learner)
    builder.add_node("collect_reference_material", collect_reference_material)
    builder.add_node("create_quick_lesson", create_quick_lesson)
    builder.add_node("create_deep_lesson", create_deep_lesson)
    builder.add_node("build_quiz", build_quiz)
    builder.add_node("wrap_up", wrap_up)

    builder.add_edge(START, "diagnose_learner")
    builder.add_edge("diagnose_learner", "collect_reference_material")
    builder.add_conditional_edges("collect_reference_material", route_lesson_mode)
    builder.add_edge("create_quick_lesson", "build_quiz")
    builder.add_edge("create_deep_lesson", "build_quiz")
    builder.add_edge("build_quiz", "wrap_up")
    builder.add_edge("wrap_up", END)

    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    sample_state = build_initial_state(
        topic="Python 함수",
        goal="함수를 직접 정의하고 호출할 수 있다",
        learner_level="beginner",
        available_minutes=30,
    )
    result = graph.invoke(sample_state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
