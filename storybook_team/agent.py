import base64
import json
import mimetypes
import os
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.context import Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.events.event import Event
from google.genai import types

from .prompts import (
    ILLUSTRATION_PROMPT_TEMPLATE,
    STORY_WRITER_INSTRUCTION,
)

TEXT_MODEL = os.getenv("STORYBOOK_TEXT_MODEL", "gpt-5-mini")
IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gpt-image-1")
STORY_STATE_KEY = "storybook_story_json"
ILLUSTRATION_STATE_KEY = "storybook_illustrations"
FINAL_BOOK_STATE_KEY = "storybook_final_book"
PROGRESS_LOG_STATE_KEY = "storybook_progress_log"
ILLUSTRATION_PAGE_STATE_PREFIX = "storybook_illustration_page_"
PROGRESS_STATUS_PREFIX = "storybook_progress_status_"
PAGE_COUNT = 5


class StoryPage(BaseModel):
    page_number: int
    text: str
    visual_description: str


class StorybookStory(BaseModel):
    title: str
    theme: str
    target_age: str
    pages: list[StoryPage] = Field(min_length=PAGE_COUNT, max_length=PAGE_COUNT)


def _openai_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required.")
    return AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _content(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=text)])


def _text_event(
    ctx: InvocationContext,
    author: str,
    text: str,
    *,
    actions: Any | None = None,
) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=_content(text),
        actions=actions,
    )


def _page_state_key(page_number: int) -> str:
    return f"{ILLUSTRATION_PAGE_STATE_PREFIX}{page_number}"


def _progress_state_key(step_name: str) -> str:
    return f"{PROGRESS_STATUS_PREFIX}{step_name}"


def _set_progress(tool_context: Context, step_name: str, message: str) -> None:
    tool_context.state[_progress_state_key(step_name)] = message


def _collect_progress_entries(tool_context: Context) -> list[str]:
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


def _normalize_story(story: StorybookStory) -> StorybookStory:
    ordered_pages = sorted(story.pages, key=lambda page: page.page_number)
    if [page.page_number for page in ordered_pages] != list(range(1, PAGE_COUNT + 1)):
        raise ValueError(f"Story pages must be numbered 1 through {PAGE_COUNT}.")

    for page in ordered_pages:
        if not page.text.strip() or not page.visual_description.strip():
            raise ValueError("Each page needs text and visual_description.")

    return story.model_copy(update={"pages": ordered_pages})


def _load_story(raw_story: str | None) -> StorybookStory:
    if not raw_story:
        raise ValueError(f"Shared state `{STORY_STATE_KEY}` is empty.")
    parsed = StorybookStory.model_validate_json(raw_story)
    return _normalize_story(parsed)


def _load_json_state(raw_text: str | None, error_message: str) -> dict[str, Any]:
    if not raw_text:
        raise ValueError(error_message)
    data = json.loads(raw_text)
    if not isinstance(data, dict):
        raise ValueError(error_message)
    return data


def _image_extension(mime_type: str) -> str:
    extension = mimetypes.guess_extension(mime_type)
    if extension == ".jpe":
        return ".jpg"
    return extension or ".png"


def _save_page_illustration(
    tool_context: Context,
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


def _build_illustration_index(tool_context: Context) -> dict[str, Any]:
    story = _load_story(tool_context.state.get(STORY_STATE_KEY))
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
        "title": story.title,
        "theme": story.theme,
        "image_model": IMAGE_MODEL,
        "pages": pages,
    }


class OpenAIStoryWriterAgent(BaseAgent):
    model: str = TEXT_MODEL

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        agent_context = Context(ctx)
        user_prompt = ""
        if agent_context.user_content and agent_context.user_content.parts:
            user_prompt = " ".join(
                part.text
                for part in agent_context.user_content.parts
                if getattr(part, "text", None)
            ).strip()

        client = _openai_client()
        response = await client.responses.parse(
            model=self.model,
            input=user_prompt,
            instructions=STORY_WRITER_INSTRUCTION,
            text_format=StorybookStory,
        )
        story = _normalize_story(
            response.output_parsed
            or StorybookStory.model_validate_json(response.output_text)
        )
        agent_context.state[STORY_STATE_KEY] = story.model_dump_json(ensure_ascii=False)
        yield _text_event(
            ctx,
            self.name,
            f"스토리 초안 생성 완료: {story.title}",
            actions=agent_context.actions,
        )

    async def _run_live_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported.")
        yield


class OpenAIIllustrationAgent(BaseAgent):
    page_number: int
    model: str = IMAGE_MODEL

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        agent_context = Context(ctx)
        story = _load_story(agent_context.state.get(STORY_STATE_KEY))
        page = next(
            item for item in story.pages if item.page_number == self.page_number
        )
        prompt = ILLUSTRATION_PROMPT_TEMPLATE.format(
            title=story.title,
            page_number=page.page_number,
            visual_description=page.visual_description,
            text=page.text,
        )

        client = _openai_client()
        response = await client.images.generate(
            model=self.model,
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            output_format="png",
        )
        if not response.data or not response.data[0].b64_json:
            raise ValueError(f"Image generation failed for page {self.page_number}.")

        image_bytes = base64.b64decode(response.data[0].b64_json)
        mime_type = "image/png"
        filename = f"page_{self.page_number:02d}{_image_extension(mime_type)}"

        await agent_context.save_artifact(
            filename=filename,
            artifact=types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        )
        _save_page_illustration(
            agent_context,
            page_number=self.page_number,
            filename=filename,
            mime_type=mime_type,
            prompt=prompt,
        )
        _set_progress(
            agent_context,
            f"image_{self.page_number}_done",
            f"이미지 {self.page_number}/{PAGE_COUNT} 생성 완료",
        )

        yield _text_event(
            ctx,
            self.name,
            f"이미지 {self.page_number}/{PAGE_COUNT} 생성 완료: {filename}",
            actions=agent_context.actions,
        )

    async def _run_live_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported.")
        yield


class StorybookAssemblerAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        callback_context = Context(ctx)
        story = _load_story(callback_context.state.get(STORY_STATE_KEY))
        illustration_index = _build_illustration_index(callback_context)
        callback_context.state[ILLUSTRATION_STATE_KEY] = json.dumps(
            illustration_index,
            ensure_ascii=False,
        )

        image_pages = illustration_index.get("pages", {})
        missing_pages = [
            str(page.page_number)
            for page in story.pages
            if str(page.page_number) not in image_pages
        ]
        if missing_pages:
            raise ValueError(
                f"Missing illustration artifacts for pages: {', '.join(missing_pages)}"
            )

        progress_entries = _collect_progress_entries(callback_context)
        callback_context.state[PROGRESS_LOG_STATE_KEY] = json.dumps(
            progress_entries,
            ensure_ascii=False,
        )

        lines = [
            f"# {story.title}",
            "",
            f"- 테마: {story.theme}",
            f"- 추천 연령: {story.target_age}",
            "",
        ]
        for page in story.pages:
            image_record = image_pages[str(page.page_number)]
            lines.extend(
                [
                    f"## 페이지 {page.page_number}",
                    page.text,
                    f"삽화 파일: {image_record['filename']}",
                    "",
                ]
            )

        if progress_entries:
            lines.extend(["## 진행 로그", *[f"- {entry}" for entry in progress_entries], ""])

        storybook_markdown = "\n".join(lines).strip()
        callback_context.state[FINAL_BOOK_STATE_KEY] = storybook_markdown
        yield _text_event(
            ctx,
            self.name,
            storybook_markdown,
            actions=callback_context.actions,
        )

    async def _run_live_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported.")
        yield


async def _before_story_writer(callback_context: Context) -> None:
    _set_progress(callback_context, "story_start", "스토리 작성 중...")
    return None


async def _after_story_writer(callback_context: Context) -> types.Content:
    story = _load_story(callback_context.state.get(STORY_STATE_KEY))
    _set_progress(callback_context, "story_done", "스토리 작성 완료")
    return _content(f"스토리 작성 완료: '{story.title}' 5페이지 구성이 준비되었습니다.")


def _before_parallel_illustration(callback_context: Context) -> None:
    _set_progress(callback_context, "parallel_start", "삽화 병렬 생성 시작")
    return None


def _after_parallel_illustration(callback_context: Context) -> types.Content:
    illustration_index = _build_illustration_index(callback_context)
    callback_context.state[ILLUSTRATION_STATE_KEY] = json.dumps(
        illustration_index,
        ensure_ascii=False,
    )
    _set_progress(callback_context, "parallel_done", "삽화 병렬 생성 완료")
    generated = sorted(
        item["filename"]
        for item in illustration_index.get("pages", {}).values()
        if isinstance(item, dict)
    )
    return _content(f"삽화 생성 완료: {len(generated)}/{PAGE_COUNT}장, " + ", ".join(generated))


def _make_before_page_callback(page_number: int):
    async def before_page(callback_context: Context) -> None:
        _set_progress(
            callback_context,
            f"image_{page_number}_start",
            f"이미지 {page_number}/{PAGE_COUNT} 생성 중...",
        )
        return None

    return before_page


story_writer_agent = OpenAIStoryWriterAgent(
    name="StoryWriterAgent",
    description="Writes a five-page children's story with the OpenAI Responses API.",
    before_agent_callback=_before_story_writer,
    after_agent_callback=_after_story_writer,
)

illustration_agents: list[OpenAIIllustrationAgent] = []
for page_number in range(1, PAGE_COUNT + 1):
    illustration_agents.append(
        OpenAIIllustrationAgent(
            name=f"IllustratorPage{page_number}Agent",
            description=f"Generates the illustration for page {page_number} with the OpenAI Images API.",
            page_number=page_number,
            before_agent_callback=_make_before_page_callback(page_number),
        )
    )

parallel_illustrator_agent = ParallelAgent(
    name="IllustrationParallelAgent",
    description="Generates the five storybook illustrations in parallel.",
    sub_agents=illustration_agents,
    before_agent_callback=_before_parallel_illustration,
    after_agent_callback=_after_parallel_illustration,
)

book_assembler_agent = StorybookAssemblerAgent(
    name="BookAssemblerAgent",
    description="Assembles the final storybook markdown from story state and image artifacts.",
)

root_agent = SequentialAgent(
    name="storybook_pipeline",
    description=(
        "Creates a five-page children's story, generates five illustrations in "
        "parallel, and assembles a complete storybook with OpenAI APIs."
    ),
    sub_agents=[
        story_writer_agent,
        parallel_illustrator_agent,
        book_assembler_agent,
    ],
)
