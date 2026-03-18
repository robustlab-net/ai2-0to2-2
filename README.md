## Storybook Team

Google ADK로 만든 두 에이전트 파이프라인입니다.

- `StoryWriterAgent`: 사용자의 테마를 받아 5페이지 어린이 동화를 JSON으로 작성하고 state에 저장합니다.
- `IllustratorAgent`: state에 저장된 스토리 JSON을 읽고 각 페이지 이미지를 생성해 artifact로 저장합니다.

구현 위치:

- `storybook_team/agent.py`
- `storybook_team/prompts.py`

## Setup

```bash
uv sync
```

환경 변수:

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

선택 설정:

```bash
export STORYBOOK_TEXT_MODEL="gemini-2.5-flash"
export STORYBOOK_IMAGE_MODEL="gemini-2.5-flash-image"
```

## Test With ADK Web

ADK 문서에 따르면 `adk web`은 에이전트 폴더를 포함하는 상위 디렉터리에서 실행해야 합니다.

```bash
uv run adk web
```

브라우저에서 Web UI를 열고 `storybook_team`을 선택한 뒤 다음처럼 입력하면 됩니다.

```text
용감한 다람쥐가 달빛 숲에서 친구를 찾는 이야기로 동화책을 만들어줘.
```

실행 후 기대 결과:

- state의 `storybook_story_json`에 5페이지 스토리 JSON 저장
- state의 `storybook_illustrations`에 생성 결과 요약 저장
- artifact에 `page_01.png` 같은 페이지 이미지 저장
