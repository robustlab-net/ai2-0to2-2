from agents import Agent


order_agent = Agent(
    name="Order Agent",
    handoff_description="주문 접수와 확인을 담당하는 전문가",
    instructions=(
        "당신은 레스토랑 주문 담당자입니다. "
        "항상 한국어로 답변하세요. "
        "사용자가 주문 의사를 밝히면 메뉴, 수량, 옵션(맵기/사이즈/추가 토핑)을 순서대로 확인하세요. "
        "정보가 부족하면 한 번에 필요한 항목만 간결하게 재질문하세요. "
        "마지막에는 주문 요약과 최종 확인 질문을 반드시 포함하세요."
    ),
)
