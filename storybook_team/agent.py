import json
import mimetypes
import os
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from .prompts import (
    BOOK_ASSEMBLER_DESCRIPTION,
    BOOK_ASSEMBLER_INSTRUCTION,
    ILLUSTRATION_AGENT_DESCRIPTION,
    ILLUSTRATION_AGENT_INSTRUCTION,
    STORY_WRITER_DESCRIPTION,
    STORY_WRITER_INSTRUCTION,
)

TEXT_MODEL = os.getenv("STORYBOOK_TEXT_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gemini-2.5-flash-image")
STORY_STATE_KEY = "storybook_story_json"
ILLUSTRATION_STATE_KEY = "storybook_illustrations"
FINAL_BOOK_STATE_KEY = "storybook_final_book"
PROGRESS_LOG_STATE_KEY = "storybook_progress_log"
ILLUSTRATION_PAGE_STATE_PREFIX = "storybook_illustration_page_"
PROGRESS_STATUS_PREFIX = "storybook_progress_status_"
PAGE_COUNT = 5


def _strip_code_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def _load_json_state(raw_text: str, error_message: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(raw_text)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError(error_message)
    return data


def _load_story_from_state(raw_story: str) -> dict[str, Any]:
    data = _load_json_state(raw_story, "Story JSON must be an object.")
    pages = data.get("pages")
    if not isinstance(pages, list) or len(pages) != PAGE_COUNT:
        raise ValueError(f"Story JSON must include exactly {PAGE_COUNT} pages.")

    normalized_pages: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ValueError("Each page must be an object.")

        page_number = page.get("page_number", index)
        text = str(page.get("text", "")).strip()
        visual_description = str(page.get("visual_description", "")).strip()
        if not text or not visual_description:
            raise ValueError("Each page needs text and visual_description.")

        normalized_pages.append(
            {
                "page_number": int(page_number),
                "text": text,
                "visual_description": visual_description,
            }
        )

    data["pages"] = sorted(normalized_pages, key=lambda item: item["page_number"])
    return data


def _load_illustration_index(raw_data: str | None) -> dict[str, Any]:
    if not raw_data:
        return {"pages": {}}

    data = _load_json_state(raw_data, "Illustration JSON must be an object.")
    pages = data.get("pages")
    if not isinstance(pages, dict):
        data["pages"] = {}
    return data


def _page_state_key(page_number: int) -> str:
    return f"{ILLUSTRATION_PAGE_STATE_PREFIX}{page_number}"


def _progress_state_key(step_name: str) -> str:
    return f"{PROGRESS_STATUS_PREFIX}{step_name}"


def _save_page_illustration(
    tool_context: ToolContext | Context,
    *,
    page_number: int,
    filename: str,
    mime_type: str,
    prompt: str,
) -> None:
    tool_context.state[_page_state_key(page_number)] = json.dumps(
        {
            "page_number": page_number,
            "filename": filename,
            "mime_type": mime_type,
            "prompt": prompt,
        },
        ensure_ascii=False,
    )


def _set_progress(tool_context: ToolContext | Context, step_name: str, message: str) -> None:
    tool_context.state[_progress_state_key(step_name)] = message


def _collect_progress_entries(tool_context: ToolContext | Context) -> list[str]:
    ordered_keys = ["story_start", "story_done", "parallel_start"]
    for page_number in range(1, PAGE_COUNT + 1):
        ordered_keys.append(f"image_{page_number}_start")
        ordered_keys.append(f"image_{page_number}_done")
    ordered_keys.append("parallel_done")

    entries: list[str] = []
    for key in ordered_keys:
        message = tool_context.state.get(_progress_state_key(key))
        if message:
            entries.append(str(message))
    return entries


def _build_illustration_index(tool_context: ToolContext | Context) -> dict[str, Any]:
    raw_story = tool_context.state.get(STORY_STATE_KEY)
    story = _load_story_from_state(raw_story) if raw_story else {}
    pages: dict[str, Any] = {}

    for page_number in range(1, PAGE_COUNT + 1):
        raw_page = tool_context.state.get(_page_state_key(page_number))
        if not raw_page:
            continue
        pages[str(page_number)] = _load_json_state(
            raw_page,
            "Illustration page JSON must be an object.",
        )

    return {
        "title": str(story.get("title", "Untitled Story")).strip() or "Untitled Story",
        "theme": str(story.get("theme", "")).strip(),
        "image_model": IMAGE_MODEL,
        "pages": pages,
    }


def _progress_content(message: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=message)])


def _image_extension(mime_type: str) -> str:
    extension = mimetypes.guess_extension(mime_type)
    if extension == ".jpe":
        return ".jpg"
    return extension or ".png"


def _build_page_prompt(story: dict[str, Any], page: dict[str, Any]) -> str:
    title = str(story.get("title", "Untitled Story")).strip() or "Untitled Story"
    page_number = int(page["page_number"])
    return (
        "Children's picture book illustration, soft expressive shapes, warm lighting, "
        "gentle emotions, highly readable composition for kids. "
        f"Story title: {title}. "
        f"Page {page_number}. "
        f"Scene description: {page['visual_description']} "
        f"Story text: {page['text']} "
        "Create a polished full-page illustration with no text, no watermark, and a consistent character design."
    )


async def _generate_page_illustration(
    *,
    tool_context: ToolContext,
    page_number: int,
) -> dict[str, Any]:
    raw_story = tool_context.state.get(STORY_STATE_KEY)
    if not raw_story:
        raise ValueError(f"Shared state `{STORY_STATE_KEY}` is empty.")

    story = _load_story_from_state(raw_story)
    page = next(
        (item for item in story["pages"] if int(item["page_number"]) == page_number),
        None,
    )
    if page is None:
        raise ValueError(f"Page {page_number} was not found in story state.")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required to generate illustrations.")

    prompt = _build_page_prompt(story, page)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    image_part = next(
        (part for part in response.parts if getattr(part, "inline_data", None)),
        None,
    )
    if image_part is None or image_part.inline_data is None:
        raise ValueError(f"Image generation failed for page {page_number}.")

    mime_type = image_part.inline_data.mime_type or "image/png"
    filename = f"page_{page_number:02d}{_image_extension(mime_type)}"

    await tool_context.save_artifact(
        filename=filename,
        artifact=types.Part.from_bytes(
            data=image_part.inline_data.data,
            mime_type=mime_type,
        ),
    )

    _save_page_illustration(
        tool_context,
        page_number=page_number,
        filename=filename,
        mime_type=mime_type,
        prompt=prompt,
    )
    _set_progress(
        tool_context,
        f"image_{page_number}_done",
        f"이미지 {page_number}/{PAGE_COUNT} 생성 완료",
    )

    return {
        "page_number": page_number,
        "filename": filename,
        "mime_type": mime_type,
    }


def _make_illustration_tool(page_number: int):
    async def generate_page_image(tool_context: ToolContext) -> dict[str, Any]:
        return await _generate_page_illustration(
            tool_context=tool_context,
            page_number=page_number,
        )

    generate_page_image.__name__ = f"generate_page_{page_number}_image"
    generate_page_image.__doc__ = (
        f"Generate the illustration artifact for page {page_number} of the current story."
    )
    return generate_page_image


async def assemble_storybook(tool_context: ToolContext) -> str:
    raw_story = tool_context.state.get(STORY_STATE_KEY)
    if not raw_story:
        raise ValueError(f"Shared state `{STORY_STATE_KEY}` is empty.")

    story = _load_story_from_state(raw_story)
    illustration_index = _load_illustration_index(tool_context.state.get(ILLUSTRATION_STATE_KEY))
    image_pages = illustration_index.get("pages", {})

    missing_pages = [
        str(page["page_number"])
        for page in story["pages"]
        if str(page["page_number"]) not in image_pages
    ]
    if missing_pages:
        raise ValueError(f"Missing illustration artifacts for pages: {', '.join(missing_pages)}")

    lines = [
        f"# {story['title']}",
        "",
        f"- 테마: {story.get('theme', '')}",
        f"- 추천 연령: {story.get('target_age', '')}",
        "",
    ]
    for page in story["pages"]:
        page_number = int(page["page_number"])
        image_record = image_pages[str(page_number)]
        lines.extend(
            [
                f"## 페이지 {page_number}",
                page["text"],
                f"삽화 파일: {image_record['filename']}",
                "",
            ]
        )

    progress_entries = _collect_progress_entries(tool_context)
    if progress_entries:
        lines.extend(["## 진행 로그", *[f"- {entry}" for entry in progress_entries], ""])

    storybook_markdown = "\n".join(lines).strip()
    tool_context.state[PROGRESS_LOG_STATE_KEY] = json.dumps(
        progress_entries,
        ensure_ascii=False,
    )
    tool_context.state[FINAL_BOOK_STATE_KEY] = storybook_markdown
    return storybook_markdown


async def _before_story_writer(callback_context: Context) -> None:
    _set_progress(callback_context, "story_start", "스토리 작성 중...")
    return None


async def _after_story_writer(callback_context: Context) -> types.Content:
    raw_story = callback_context.state.get(STORY_STATE_KEY)
    story = _load_story_from_state(raw_story) if raw_story else {"title": "동화"}
    _set_progress(callback_context, "story_done", "스토리 작성 완료")
    return _progress_content(
        f"스토리 작성 완료: '{story['title']}' 5페이지 구성이 준비되었습니다."
    )


def _before_parallel_illustration(callback_context: Context) -> None:
    _set_progress(callback_context, "parallel_start", "삽화 병렬 생성 시작")
    return None


def _after_parallel_illustration(callback_context: Context) -> types.Content:
    illustration_index = _build_illustration_index(callback_context)
    callback_context.state[ILLUSTRATION_STATE_KEY] = json.dumps(
        illustration_index,
        ensure_ascii=False,
    )
    pages = illustration_index.get("pages", {})
    generated = sorted(
        (item["filename"] for item in pages.values() if isinstance(item, dict)),
    )
    _set_progress(callback_context, "parallel_done", "삽화 병렬 생성 완료")
    return _progress_content(
        f"삽화 생성 완료: {len(generated)}/{PAGE_COUNT}장, "
        + ", ".join(generated)
    )


def _make_before_page_callback(page_number: int):
    async def before_page(callback_context: Context) -> None:
        _set_progress(
            callback_context,
            f"image_{page_number}_start",
            f"이미지 {page_number}/{PAGE_COUNT} 생성 중...",
        )
        return None

    return before_page


def _make_after_page_callback(page_number: int):
    async def after_page(callback_context: Context) -> types.Content:
        raw_page = callback_context.state.get(_page_state_key(page_number))
        page_data = (
            _load_json_state(raw_page, "Illustration page JSON must be an object.")
            if raw_page
            else {}
        )
        filename = page_data.get("filename", f"page_{page_number:02d}.png")
        return _progress_content(
            f"이미지 {page_number}/{PAGE_COUNT} 생성 완료: {filename}"
        )

    return after_page


story_writer_agent = LlmAgent(
    name="StoryWriterAgent",
    model=TEXT_MODEL,
    description=STORY_WRITER_DESCRIPTION,
    instruction=STORY_WRITER_INSTRUCTION,
    output_key=STORY_STATE_KEY,
    before_agent_callback=_before_story_writer,
    after_agent_callback=_after_story_writer,
)

illustration_agents: list[LlmAgent] = []
for page_number in range(1, PAGE_COUNT + 1):
    illustration_agents.append(
        LlmAgent(
            name=f"IllustratorPage{page_number}Agent",
            model=TEXT_MODEL,
            description=ILLUSTRATION_AGENT_DESCRIPTION.format(page_number=page_number),
            instruction=ILLUSTRATION_AGENT_INSTRUCTION.format(page_number=page_number),
            tools=[_make_illustration_tool(page_number)],
            before_agent_callback=_make_before_page_callback(page_number),
            after_agent_callback=_make_after_page_callback(page_number),
        )
    )

parallel_illustrator_agent = ParallelAgent(
    name="IllustrationParallelAgent",
    description="Generates the five storybook illustrations in parallel.",
    sub_agents=illustration_agents,
    before_agent_callback=_before_parallel_illustration,
    after_agent_callback=_after_parallel_illustration,
)

book_assembler_agent = LlmAgent(
    name="BookAssemblerAgent",
    model=TEXT_MODEL,
    description=BOOK_ASSEMBLER_DESCRIPTION,
    instruction=BOOK_ASSEMBLER_INSTRUCTION,
    tools=[assemble_storybook],
    output_key=FINAL_BOOK_STATE_KEY,
)

root_agent = SequentialAgent(
    name="storybook_pipeline",
    description=(
        "Creates a five-page children's story, generates five illustrations in "
        "parallel, and assembles a complete storybook."
    ),
    sub_agents=[
        story_writer_agent,
        parallel_illustrator_agent,
        book_assembler_agent,
    ],
)
