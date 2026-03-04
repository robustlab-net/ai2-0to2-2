import asyncio
import datetime as dt
import dotenv
import json
import os
import streamlit as st
from openai import OpenAI

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
FileSearchTool = getattr(agents, "FileSearchTool", None)

st.set_page_config(page_title="Life Coach Agent", page_icon="🧭", layout="centered")
st.title("🧭 Life Coach Agent")
st.caption("동기부여, 자기개발, 습관 형성을 돕는 코치")

SESSION_ID = "life-coach-session"
DB_PATH = "life-coach-memory.db"
PROGRESS_LOG_PATH = "progress_log.jsonl"
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "")

client = OpenAI()

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(SESSION_ID, DB_PATH)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "agent" not in st.session_state:
    tools = []
    if WebSearchTool is not None:
        tools.append(WebSearchTool())
    if FileSearchTool is not None and VECTOR_STORE_ID:
        tools.append(
            FileSearchTool(
                vector_store_ids=[VECTOR_STORE_ID],
                max_num_results=5,
            )
        )

    st.session_state["agent"] = Agent(
        name="Life Coach",
        instructions=(
            "You are an empathetic and motivating life coach. "
            "Always answer in Korean unless the user asks another language. "
            "Give practical, concrete steps. "
            "The user stores personal goals and diary notes in uploaded files. "
            "When the user asks about progress, goals, habits, or past records, use file search first "
            "to retrieve relevant personal context, then tailor your advice to those records. "
            "When useful, combine file search with web search for current evidence-based recommendations. "
            "For progress check-ins, mention what changed over time based on dated records if available. "
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


def log_progress(entry_type: str, note: str) -> None:
    record = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "entry_type": entry_type,
        "note": note[:180],
    }
    with open(PROGRESS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_progress_logs() -> list[dict]:
    if not os.path.exists(PROGRESS_LOG_PATH):
        return []
    logs: list[dict] = []
    with open(PROGRESS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return logs


def upload_to_vector_store(file_name: str, content: bytes) -> None:
    uploaded_file = client.files.create(
        file=(file_name, content),
        purpose="user_data",
    )
    client.vector_stores.files.create(
        vector_store_id=VECTOR_STORE_ID,
        file_id=uploaded_file.id,
    )


def update_status(status_container, event_name: str) -> None:
    status_messages = {
        "response.web_search_call.in_progress": ("🔍 웹 검색 시작...", "running"),
        "response.web_search_call.searching": ("🔍 웹 검색 중...", "running"),
        "response.web_search_call.completed": ("✅ 웹 검색 완료", "complete"),
        "response.file_search_call.in_progress": ("🗂️ 개인 기록 검색 시작...", "running"),
        "response.file_search_call.searching": ("🗂️ 개인 기록 검색 중...", "running"),
        "response.file_search_call.completed": ("✅ 개인 기록 검색 완료", "complete"),
        "response.completed": ("완료", "complete"),
    }
    if event_name in status_messages:
        label, state = status_messages[event_name]
        status_container.update(label=label, state=state)


async def run_agent(user_message: str) -> str:
    stream = Runner.run_streamed(agent, user_message, session=session)
    chunks: list[str] = []

    with st.chat_message("assistant"):
        status_container = st.status("⏳ 응답 생성 중...", expanded=False)
        placeholder = st.empty()
        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                event_name = getattr(event.data, "type", "")
                update_status(status_container, event_name)
                if event_name == "response.output_text.delta":
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
    st.subheader("Memory")

    if WebSearchTool is None:
        st.warning("현재 SDK에서 `WebSearchTool`을 찾지 못했습니다. Agents SDK 버전을 확인해 주세요.")
    else:
        st.success("웹 검색 도구 활성화")

    if not VECTOR_STORE_ID:
        st.warning("`.env`에 `VECTOR_STORE_ID`를 설정하면 목표/일기 파일 검색을 활성화할 수 있습니다.")
    elif FileSearchTool is None:
        st.warning("현재 SDK에서 `FileSearchTool`을 찾지 못했습니다. Agents SDK 버전을 확인해 주세요.")
    else:
        st.success("파일 검색 도구 활성화")

    uploaded_docs = st.file_uploader(
        "개인 목표 문서 업로드 (PDF/TXT)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="업로드한 문서는 코치가 목표 점검 시 참조합니다.",
    )

    if st.button("목표 문서 업로드", use_container_width=True):
        if not uploaded_docs:
            st.info("업로드할 파일을 먼저 선택해 주세요.")
        elif not VECTOR_STORE_ID:
            st.error("`VECTOR_STORE_ID`가 없어 업로드할 수 없습니다.")
        else:
            for file in uploaded_docs:
                with st.status(f"⏳ `{file.name}` 업로드 중..."):
                    upload_to_vector_store(file.name, file.getvalue())
                    log_progress("goal_upload", f"목표 문서 업로드: {file.name}")
            st.success("선택한 목표 문서 업로드가 완료되었습니다.")

    st.divider()
    st.caption("오늘 일기/진행 기록 저장")
    diary_text = st.text_area(
        "일기 또는 진행 메모",
        placeholder="예: 이번 주 운동 2회 완료, 수면은 평균 6시간...",
        height=120,
    )
    if st.button("일기 저장", use_container_width=True):
        if not diary_text.strip():
            st.info("저장할 내용을 입력해 주세요.")
        elif not VECTOR_STORE_ID:
            st.error("`VECTOR_STORE_ID`가 없어 저장할 수 없습니다.")
        else:
            now = dt.datetime.now()
            file_name = f"diary-{now.strftime('%Y%m%d-%H%M%S')}.txt"
            body = (
                f"Date: {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"Type: diary\n\n"
                f"{diary_text.strip()}\n"
            )
            with st.status("⏳ 일기 저장 중..."):
                upload_to_vector_store(file_name, body.encode("utf-8"))
                log_progress("diary", diary_text.strip())
            st.success("일기가 저장되었습니다. 코치가 다음 조언에서 참조할 수 있습니다.")

    st.divider()
    logs = read_progress_logs()
    st.metric("누적 기록 수", len(logs))
    if logs:
        daily_counts: dict[str, int] = {}
        for item in logs:
            day = item.get("timestamp", "")[:10]
            if not day:
                continue
            daily_counts[day] = daily_counts.get(day, 0) + 1

        chart_data = [
            {"date": day, "entries": count}
            for day, count in sorted(daily_counts.items())
        ]
        st.bar_chart(chart_data, x="date", y="entries")
        st.caption("최근 기록")
        for item in logs[-5:][::-1]:
            st.write(f"- {item['timestamp']} · {item['entry_type']} · {item['note']}")

    if st.button("Reset memory", use_container_width=True):
        asyncio.run(session.clear_session())
        st.session_state["messages"] = []
        if os.path.exists(PROGRESS_LOG_PATH):
            os.remove(PROGRESS_LOG_PATH)
        st.rerun()

    if st.button("Show memory items", use_container_width=True):
        items = asyncio.run(session.get_items())
        st.write(items)
