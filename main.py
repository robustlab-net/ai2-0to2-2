import asyncio
import os
import uuid

import dotenv
import streamlit as st
from agents import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    Runner,
    SQLiteSession,
)

from models import UserAccountContext
from my_agents.triage_agent import triage_agent


dotenv.load_dotenv()

st.set_page_config(page_title="Restaurant Bot", page_icon="🍽️", layout="centered")

AGENT_COLORS = {
    "Triage Agent": "#6C4E31",
    "Menu Agent": "#2D6A4F",
    "Order Agent": "#8D0801",
    "Reservation Agent": "#005F73",
    "Complaints Agent": "#9A3412",
    "Guardrail": "#7F1D1D",
}
DB_PATH = "restaurant-memory.db"


def resolve_api_key() -> str | None:
    secrets_key = st.secrets.get("OPENAI_API_KEY")
    env_key = os.getenv("OPENAI_API_KEY")
    return secrets_key or env_key


def ensure_runtime_secrets() -> None:
    api_key = resolve_api_key()
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        return

    st.error("`OPENAI_API_KEY`가 필요합니다. `.streamlit/secrets.toml` 또는 배포 Secrets에 추가하세요.")
    st.stop()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .hero {
            padding: 1.1rem 1.2rem;
            border-radius: 18px;
            background:
                radial-gradient(circle at top left, rgba(200, 75, 49, 0.18), transparent 32%),
                linear-gradient(135deg, #fff7ed 0%, #fff1e6 100%);
            border: 1px solid rgba(108, 78, 49, 0.16);
            margin-bottom: 1rem;
        }
        .hero-title {
            font-size: 1.65rem;
            font-weight: 700;
            color: #2b211b;
            margin-bottom: 0.3rem;
        }
        .hero-copy {
            color: #4b3a2f;
            font-size: 0.96rem;
            line-height: 1.5;
        }
        .agent-chip {
            display: inline-block;
            padding: 0.28rem 0.62rem;
            border-radius: 999px;
            color: white;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            margin-bottom: 0.45rem;
        }
        .status-card {
            padding: 0.85rem 1rem;
            border-radius: 14px;
            background: #f8efe6;
            border: 1px solid rgba(108, 78, 49, 0.12);
            margin-bottom: 1rem;
        }
        .status-label {
            font-size: 0.78rem;
            color: #7c6758;
            margin-bottom: 0.2rem;
        }
        .status-value {
            font-size: 1rem;
            font-weight: 700;
            color: #2b211b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_agent_chip(agent_name: str) -> str:
    color = AGENT_COLORS.get(agent_name, "#6B7280")
    return f"<span class='agent-chip' style='background:{color};'>{agent_name}</span>"


def guardrail_message(exc: Exception) -> str:
    result = getattr(exc, "guardrail_result", None)
    output = getattr(result, "output", None)
    info = getattr(output, "output_info", None)
    if isinstance(info, str) and info.strip():
        return info.strip()
    return "해당 요청은 현재 처리할 수 없습니다."


def init_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = f"restaurant-{uuid.uuid4().hex}"

    if "session" not in st.session_state:
        st.session_state["session"] = SQLiteSession(
            st.session_state["session_id"],
            DB_PATH,
        )

    if "agent" not in st.session_state:
        st.session_state["agent"] = triage_agent

    if "display_messages" not in st.session_state:
        st.session_state["display_messages"] = []


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Restaurant Bot</div>
            <div class="hero-copy">
                Triage Agent가 요청을 분류하고 Menu, Order, Reservation, Complaints 전문 에이전트로
                즉시 연결합니다. 입력과 출력은 guardrail로 검사되고, 대화 메모리는 세션별로 유지됩니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="status-card">
            <div class="status-label">현재 활성 에이전트</div>
            <div class="status-value">{st.session_state['agent'].name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def paint_history() -> None:
    for message in st.session_state["display_messages"]:
        role = message["role"]
        with st.chat_message(role):
            if role == "assistant":
                st.markdown(render_agent_chip(message["agent_name"]), unsafe_allow_html=True)
            st.write(message["content"])


def handoff_message(new_agent_name: str) -> str:
    mapping = {
        "Menu Agent": "메뉴 전문가에게 연결합니다.",
        "Order Agent": "주문 담당에게 연결합니다.",
        "Reservation Agent": "예약 담당에게 연결합니다.",
        "Complaints Agent": "불만 접수 담당에게 연결합니다.",
        "Triage Agent": "접수 담당으로 돌아갑니다.",
    }
    return mapping.get(new_agent_name, f"{new_agent_name}에게 연결합니다.")


async def run_agent(message: str) -> None:
    session = st.session_state["session"]

    with st.chat_message("assistant"):
        badge_placeholder = st.empty()
        handoff_placeholder = st.empty()
        text_placeholder = st.empty()

        response = ""
        current_agent = triage_agent
        badge_placeholder.markdown(
            render_agent_chip(current_agent.name),
            unsafe_allow_html=True,
        )

        try:
            stream = Runner.run_streamed(
                current_agent,
                message,
                session=session,
                context=UserAccountContext(
                    customer_id=1,
                    name="bukoi",
                    tier="basic",
                ),
            )

            async for event in stream.stream_events():
                if event.type == "raw_response_event":
                    if event.data.type == "response.output_text.delta":
                        response += event.data.delta
                        text_placeholder.write(response.replace("$", "\\$"))
                elif event.type == "agent_updated_stream_event":
                    if current_agent.name != event.new_agent.name:
                        current_agent = event.new_agent
                        st.session_state["agent"] = event.new_agent
                        badge_placeholder.markdown(
                            render_agent_chip(current_agent.name),
                            unsafe_allow_html=True,
                        )
                        handoff_placeholder.info(handoff_message(event.new_agent.name))

            final_text = response.strip() or str(stream.final_output).strip()
            if final_text:
                st.session_state["display_messages"].append(
                    {
                        "role": "assistant",
                        "content": final_text,
                        "agent_name": current_agent.name,
                    }
                )

        except InputGuardrailTripwireTriggered as exc:
            blocked = guardrail_message(exc)
            badge_placeholder.markdown(
                render_agent_chip("Guardrail"),
                unsafe_allow_html=True,
            )
            text_placeholder.warning(blocked)
            st.session_state["display_messages"].append(
                {
                    "role": "assistant",
                    "content": blocked,
                    "agent_name": "Guardrail",
                }
            )

        except OutputGuardrailTripwireTriggered as exc:
            blocked = guardrail_message(exc)
            badge_placeholder.markdown(
                render_agent_chip("Guardrail"),
                unsafe_allow_html=True,
            )
            text_placeholder.warning(blocked)
            st.session_state["display_messages"].append(
                {
                    "role": "assistant",
                    "content": blocked,
                    "agent_name": "Guardrail",
                }
            )


ensure_runtime_secrets()
init_state()
inject_styles()
render_header()
paint_history()

message = st.chat_input("예: 예약하고 싶어요 / 채식 메뉴 있어요? / 주문이 잘못 왔어요")

if message:
    st.session_state["display_messages"].append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.write(message)
    asyncio.run(run_agent(message))

with st.sidebar:
    st.subheader("Session")
    st.write(f"세션 ID: `{st.session_state['session_id'][:18]}...`")
    st.write(f"현재 에이전트: `{st.session_state['agent'].name}`")
    st.caption("메모리는 같은 브라우저 세션 동안 유지됩니다.")

    if st.button("Reset memory", use_container_width=True):
        asyncio.run(st.session_state["session"].clear_session())
        st.session_state["agent"] = triage_agent
        st.session_state["display_messages"] = []
        st.rerun()

    with st.expander("Stored memory items"):
        if st.button("Load memory snapshot", use_container_width=True):
            st.write(asyncio.run(st.session_state["session"].get_items()))
