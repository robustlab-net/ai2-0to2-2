## create
```bash
brew install python@3.13
which python3.13
# 보통 /opt/homebrew/bin/python3.13 로 나옴
uv init ai2_0to2_2 --python=/opt/homebrew/bin/python3.13

pyproject.toml에 붙여넣기
dependencies = [
    "notebook>=7.5.3",
    "python-dotenv==1.1.1",
    "openai>=1.98.0",
]

[dependency-groups]
dev = [
    "ipykernel>=6.30.0",
]
uv sync
```

## run
```bash
uv run streamlit run main.py
```