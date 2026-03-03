import asyncio
import dotenv
import streamlit as st

# Load environment variables from .env (expects OPENAI_API_KEY)
dotenv.load_dotenv()

try:
    import agents
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "`agents` 패키지가 설치되어 있지 않습니다. `pip install openai-agents streamlit` 후 다시 실행하세요."
    ) from exc


Agent = agents.Agent
Runner = agents.Runner
SQLiteSession = agents.SQLiteSession
WebSearchTool = getattr(agents, "WebSearchTool", None)

st.set_page_config(page_title="Life Coach Agent", page_icon="🧭", layout="centered")
st.title("🧭 Life Coach Agent")
st.caption("동기부여, 자기개발, 습관 형성을 돕는 코치")

SESSION_ID = "life-coach-session"
DB_PATH = "life-coach-memory.db"


if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(SESSION_ID, DB_PATH)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "agent" not in st.session_state:
    tools = []
    if WebSearchTool is not None:
        tools.append(WebSearchTool())

    st.session_state["agent"] = Agent(
        name="Life Coach",
        instructions=(
            "You are an empathetic and motivating life coach. "
            "Always answer in Korean unless the user asks another language. "
            "Give practical, concrete steps. "
            "When the user asks about motivation, self-improvement, or habit-building, "
            "use the web search tool to find recent, relevant advice before responding. "
            "Encourage the user while staying realistic and specific."
        ),
        tools=tools,
    )


agent = st.session_state["agent"]
session = st.session_state["session"]

# Render chat history saved in Streamlit session state
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


async def run_agent(user_message: str) -> str:
    stream = Runner.run_streamed(agent, user_message, session=session)
    chunks: list[str] = []

    with st.chat_message("assistant"):
        placeholder = st.empty()
        async for event in stream.stream_events():
            if (
                event.type == "raw_response_event"
                and getattr(event.data, "type", "") == "response.output_text.delta"
            ):
                chunks.append(event.data.delta)
                placeholder.markdown("".join(chunks))

    return "".join(chunks).strip()


prompt = st.chat_input("요즘 어떤 고민이 있나요?")

if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    reply = asyncio.run(run_agent(prompt))
    if not reply:
        reply = "지금 응답을 생성하지 못했어요. 잠시 후 다시 시도해 주세요."

    st.session_state["messages"].append({"role": "assistant", "content": reply})


with st.sidebar:
    st.subheader("Session")

    if WebSearchTool is None:
        st.warning("현재 SDK에서 `WebSearchTool`을 찾지 못했습니다. Agents SDK 버전을 확인해 주세요.")
    else:
        st.success("웹 검색 도구가 활성화되어 있습니다.")

    if st.button("Reset memory", use_container_width=True):
        asyncio.run(session.clear_session())
        st.session_state["messages"] = []
        st.rerun()

    if st.button("Show memory items", use_container_width=True):
        items = asyncio.run(session.get_items())
        st.write(items)
