import asyncio

import dotenv
import streamlit as st
from agents import InputGuardrailTripwireTriggered, Runner, SQLiteSession

from models import UserAccountContext
from my_agents.triage_agent import triage_agent


dotenv.load_dotenv()

st.set_page_config(page_title="Restaurant Bot", page_icon="🍽️", layout="centered")
st.title("🍽️ Restaurant Bot")
st.caption("Triage Agent가 요청을 분석해 메뉴/주문/예약 전문 에이전트로 연결합니다.")

user_account_ctx = UserAccountContext(
    customer_id=1,
    name="bukoi",
    tier="basic",
)

SESSION_NAME = "restaurant-chat-history"
DB_PATH = "restaurant-memory.db"

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(SESSION_NAME, DB_PATH)
session = st.session_state["session"]

if "agent" not in st.session_state:
    st.session_state["agent"] = triage_agent

if "last_specialist_agent_name" not in st.session_state:
    st.session_state["last_specialist_agent_name"] = ""


async def paint_history() -> None:
    messages = await session.get_items()
    for message in messages:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue

        with st.chat_message(role):
            if role == "user":
                content = message.get("content", "")
                if isinstance(content, str):
                    st.write(content)
                continue

            if message.get("type") != "message":
                continue

            content = message.get("content", [])
            text_chunks: list[str] = []
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if "text" in part:
                        text_chunks.append(part["text"])
            elif isinstance(content, str):
                text_chunks.append(content)

            merged = "".join(text_chunks).strip()
            if merged:
                st.write(merged.replace("$", "\\$"))


asyncio.run(paint_history())


def handoff_message(new_agent_name: str) -> str:
    mapping = {
        "Menu Agent": "메뉴 전문가에게 연결합니다...",
        "Order Agent": "주문 담당에게 연결합니다...",
        "Reservation Agent": "예약 담당에게 연결합니다...",
        "Triage Agent": "접수 담당으로 다시 연결합니다...",
    }
    return mapping.get(new_agent_name, f"{new_agent_name}에게 연결합니다...")


async def run_agent(message: str) -> None:
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        response = ""
        current_agent = triage_agent

        try:
            stream = Runner.run_streamed(
                current_agent,
                message,
                session=session,
                context=user_account_ctx,
            )

            async for event in stream.stream_events():
                if event.type == "raw_response_event":
                    if event.data.type == "response.output_text.delta":
                        response += event.data.delta
                        text_placeholder.write(response.replace("$", "\\$"))

                elif event.type == "agent_updated_stream_event":
                    if current_agent.name != event.new_agent.name:
                        should_show_handoff = (
                            event.new_agent.name == "Triage Agent"
                            or st.session_state["last_specialist_agent_name"] != event.new_agent.name
                        )
                        if should_show_handoff:
                            st.info(handoff_message(event.new_agent.name))
                        if event.new_agent.name != "Triage Agent":
                            st.session_state["last_specialist_agent_name"] = event.new_agent.name
                        current_agent = event.new_agent
                        st.session_state["agent"] = event.new_agent

        except InputGuardrailTripwireTriggered:
            st.write("해당 요청은 처리할 수 없습니다.")


message = st.chat_input("요청을 입력하세요 (예: 예약하고 싶어요 / 채식 메뉴 있어요?)")

if message:
    with st.chat_message("user"):
        st.write(message)
    asyncio.run(run_agent(message))


with st.sidebar:
    st.subheader("Session")
    st.write(f"현재 에이전트: `{st.session_state['agent'].name}`")

    if st.button("Reset memory", use_container_width=True):
        asyncio.run(session.clear_session())
        st.session_state["agent"] = triage_agent
        st.rerun()

    if st.button("Show memory items", use_container_width=True):
        st.write(asyncio.run(session.get_items()))
