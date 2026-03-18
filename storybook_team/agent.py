import json
import mimetypes
import os
from typing import Any

from google import genai
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from .prompts import (
    ILLUSTRATOR_DESCRIPTION,
    ILLUSTRATOR_INSTRUCTION,
    STORY_WRITER_DESCRIPTION,
    STORY_WRITER_INSTRUCTION,
)

TEXT_MODEL = os.getenv("STORYBOOK_TEXT_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gemini-2.5-flash-image")
STORY_STATE_KEY = "storybook_story_json"
ILLUSTRATION_STATE_KEY = "storybook_illustrations"


def _strip_code_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def _load_story_from_state(raw_story: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(raw_story)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Story JSON must be an object.")

    pages = data.get("pages")
    if not isinstance(pages, list) or len(pages) != 5:
        raise ValueError("Story JSON must include exactly 5 pages.")

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

    data["pages"] = normalized_pages
    return data


def _image_extension(mime_type: str) -> str:
    extension = mimetypes.guess_extension(mime_type)
    if extension == ".jpe":
        return ".jpg"
    return extension or ".png"


async def illustrate_story_pages(tool_context: ToolContext) -> dict[str, Any]:
    """Generate one storybook illustration per page from the shared story state."""
    raw_story = tool_context.state.get(STORY_STATE_KEY)
    if not raw_story:
        raise ValueError(f"Shared state `{STORY_STATE_KEY}` is empty.")

    story = _load_story_from_state(raw_story)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required to generate illustrations.")

    client = genai.Client(api_key=api_key)
    title = str(story.get("title", "Untitled Story")).strip() or "Untitled Story"

    illustration_records: list[dict[str, Any]] = []
    for page in story["pages"]:
        page_number = int(page["page_number"])
        prompt = (
            "Children's picture book illustration, soft expressive shapes, warm lighting, "
            "gentle emotions, highly readable composition for kids. "
            f"Story title: {title}. "
            f"Page {page_number}. "
            f"Scene description: {page['visual_description']} "
            f"Story text: {page['text']} "
            "Create a polished full-page illustration with no text, no watermark, and a consistent character design."
        )

        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
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

        illustration_records.append(
            {
                "page_number": page_number,
                "filename": filename,
                "mime_type": mime_type,
                "prompt": prompt,
            }
        )

    tool_context.state[ILLUSTRATION_STATE_KEY] = json.dumps(
        {
            "title": title,
            "theme": story.get("theme", ""),
            "image_model": IMAGE_MODEL,
            "pages": illustration_records,
        },
        ensure_ascii=False,
    )

    return {
        "title": title,
        "generated_count": len(illustration_records),
        "files": [item["filename"] for item in illustration_records],
    }


story_writer_agent = LlmAgent(
    name="StoryWriterAgent",
    model=TEXT_MODEL,
    description=STORY_WRITER_DESCRIPTION,
    instruction=STORY_WRITER_INSTRUCTION,
    output_key=STORY_STATE_KEY,
)

illustrator_agent = LlmAgent(
    name="IllustratorAgent",
    model=TEXT_MODEL,
    description=ILLUSTRATOR_DESCRIPTION,
    instruction=ILLUSTRATOR_INSTRUCTION,
    tools=[illustrate_story_pages],
    output_key="storybook_result",
)

root_agent = SequentialAgent(
    name="storybook_pipeline",
    description="Creates a five-page children's story and then generates page illustrations from shared state.",
    sub_agents=[story_writer_agent, illustrator_agent],
)
