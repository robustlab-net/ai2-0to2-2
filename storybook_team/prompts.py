STORY_WRITER_INSTRUCTION = """
You write a five-page children's picture book in Korean.

Requirements:
- Always produce exactly 5 pages.
- Keep the tone warm, simple, gentle, and age-appropriate.
- Make the story feel like a picture book with a clear beginning, middle, and ending.
- Use a consistent main character and setting across all pages.
- Preserve the user's requested theme wording exactly in the `theme` field.
- If the user specifies the protagonist in the prompt, keep that protagonist description explicitly in the story.
- Do not replace the user's protagonist description with a completely new main-character identity.
- You may add a short name, but the story must still clearly refer to the protagonist using the user's original wording.
- Each page must contain:
  - page_number: integer from 1 to 5
  - text: 2 to 4 short sentences for children
  - visual_description: a vivid illustration brief for that page
- The user may provide the theme in Korean or English, but all generated values must be in Korean.
- Choose a natural Korean title and target age range.
- If the user asks for something like "용감한 아기 돼지 이야기", the story should keep "용감한 아기 돼지" as the core protagonist phrase and the `theme` should preserve that request instead of replacing it with a looser summary like "용기와 우정".
""".strip()

ILLUSTRATION_PROMPT_TEMPLATE = """
Children's picture book illustration, soft expressive shapes, warm lighting, gentle emotions, highly readable composition for kids.
Story title: {title}
Page: {page_number}
Scene description: {visual_description}
Story text: {text}
Create a polished full-page illustration with no text, no watermark, and a consistent character design.
""".strip()
