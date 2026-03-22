## Storybook Team

Google ADK Workflow Agent로 만든 어린이 동화책 파이프라인입니다.

구성:

- `SequentialAgent`: 전체 흐름을 관리합니다.
- `StoryWriterAgent`: 사용자의 테마를 받아 5페이지 동화를 JSON으로 작성하고 state에 저장합니다.
- `ParallelAgent`: 5개의 페이지 삽화 에이전트를 동시에 실행합니다.
- `BookAssemblerAgent`: 스토리 텍스트와 삽화 artifact를 합쳐 최종 동화책 markdown을 만듭니다.
- `Callbacks`: 진행 상태를 state에 기록하고 단계 완료 메시지를 Web UI에 보여줍니다.

구현 위치:

- `storybook_team/agent.py`
- `storybook_team/prompts.py`

## Pipeline

```text
[사용자 입력]
    ↓
[SequentialAgent]
    ↓
[StoryWriterAgent]
    - 5페이지 동화 작성
    - state: storybook_story_json
    ↓
[ParallelAgent]
    - 5개 삽화 동시 생성
    - artifacts: page_01.png ... page_05.png
    - state: storybook_illustrations
    ↓
[BookAssemblerAgent]
    - 최종 동화책 markdown 조립
    - state: storybook_final_book
```

진행 로그는 `storybook_progress_log`에 저장됩니다.

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

ADK Web UI는 에이전트 폴더를 포함하는 상위 디렉터리에서 실행합니다.

```bash
uv run adk web
```

브라우저에서 Web UI를 열고 `storybook_team`을 선택한 뒤 입력합니다.

데모 1:

```text
용감한 아기 고양이 이야기로 5페이지 동화책을 만들어줘.
```

데모 2:

```text
별빛 정원을 지키는 아기 토끼 이야기로 5페이지 동화책을 만들어줘.
```

Web UI에서 기대 결과:

- 스토리 작성 단계 완료 메시지 표시
- 이미지 1/5 ~ 5/5 생성 완료 메시지 표시
- 최종 응답에 제목, 5페이지 텍스트, 각 페이지 삽화 파일명 포함
- artifact에 `page_01.png` 같은 이미지 파일 저장

## Stored Outputs

- `storybook_story_json`: 5페이지 동화 JSON
- `storybook_illustrations`: 페이지별 삽화 메타데이터
- `storybook_progress_log`: 진행 로그
- `storybook_final_book`: 완성된 동화책 markdown
