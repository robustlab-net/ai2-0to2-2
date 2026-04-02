# Education Agent

LangGraph 기반의 학습 코치 앱입니다. 사용자가 입력한 학습 주제, 목표, 수준, 가용 시간을 바탕으로 맞춤 학습 경로를 생성합니다.

## 주요 기능

- 학습 공백 진단
- 가용 시간 기반 분기
  - 40분 미만: `quick` 경로
  - 40분 이상: `deep` 경로
- 로컬 참고 노트 검색 툴 연동
- 미니 레슨 생성
- 확인 퀴즈 3문항 생성
- 다음 학습 행동 피드백 제공
- Streamlit UI에서 로딩 상태와 에러 메시지 표시

## 파일 구조

- [main.py](/Users/bcc/robustlab/ai-engineer-club/ai2_0to2_2/main.py): Streamlit 앱
- [education_agent.py](/Users/bcc/robustlab/ai-engineer-club/ai2_0to2_2/education_agent.py): LangGraph 워크플로우
- [education_reference_notes.json](/Users/bcc/robustlab/ai-engineer-club/ai2_0to2_2/education_reference_notes.json): 주제별 참고 노트
- [requirements.txt](/Users/bcc/robustlab/ai-engineer-club/ai2_0to2_2/requirements.txt): 배포용 의존성 목록

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run main.py
```

또는 `uv`를 사용할 수 있습니다.

```bash
uv sync
uv run streamlit run main.py
```

## 사용 방법

1. 학습 주제를 입력합니다.
2. 이번 학습의 목표를 입력합니다.
3. 현재 수준과 가능한 시간을 선택합니다.
4. `학습 경로 생성하기` 버튼을 누릅니다.
5. 생성된 학습 공백, 계획, 레슨, 퀴즈, 피드백을 따라 학습합니다.

## 예시 입력

- 주제: `Python 함수`
- 목표: `함수를 직접 정의하고 호출할 수 있다`
- 수준: `beginner`
- 시간: `30`

## Streamlit Cloud 배포

1. 이 저장소를 GitHub에 푸시합니다.
2. Streamlit Cloud에서 `New app`을 선택합니다.
3. 저장소는 `robustlab-net/ai2-0to2-2`, 브랜치는 배포할 브랜치를 선택합니다.
4. Main file path에 `main.py`를 입력합니다.
5. Deploy를 실행합니다.

이 앱은 별도 API 키 없이 로컬 참고 노트를 사용하므로, 기본 구성만으로 배포할 수 있습니다.

## 워크플로우 구조

```mermaid
flowchart LR
    START([START]) --> Diagnose[diagnose_learner]
    Diagnose --> Ref[collect_reference_material]
    Ref -->|available_minutes < 40| Quick[create_quick_lesson]
    Ref -->|available_minutes >= 40| Deep[create_deep_lesson]
    Quick --> Quiz[build_quiz]
    Deep --> Quiz
    Quiz --> Wrap[wrap_up]
    Wrap --> END([END])
```

## 배포 전 확인 항목

- `streamlit run main.py` 실행 가능
- 예시 입력으로 결과 생성 가능
- 에러 발생 시 사용자 안내 메시지 표시
- README 포함
