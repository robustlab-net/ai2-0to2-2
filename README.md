## Run locally
```bash
uv sync
uv run streamlit run main.py
```

## Secrets
```toml
# .streamlit/secrets.toml
OPENAI_API_KEY = "sk-..."
```

`.streamlit/secrets.toml`은 `.gitignore`에 포함되어 있으므로 커밋하지 않습니다.

## Deploy to Streamlit Community Cloud
1. GitHub 저장소에 현재 브랜치를 푸시합니다.
2. Streamlit Community Cloud에서 저장소를 선택하고 엔트리포인트를 `main.py`로 지정합니다.
3. `Advanced settings`에서 Python 3.13을 선택합니다.
4. 로컬 `.streamlit/secrets.toml` 내용을 그대로 `Secrets`에 붙여 넣습니다.
5. 배포 후 공개 URL에서 앱을 확인합니다.
