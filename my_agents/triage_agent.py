from agents import Agent, handoff
from my_agents.menu_agent import menu_agent
from my_agents.order_agent import order_agent
from my_agents.reservation_agent import reservation_agent

triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "당신은 레스토랑 접수 담당입니다. 항상 한국어로 답변하세요. "
        "사용자 의도를 분류해서 아래 담당자에게 정확히 handoff 하세요. "
        "1) 메뉴/재료/알레르기/채식: Menu Agent "
        "2) 주문 접수/변경/확인: Order Agent "
        "3) 예약/예약 변경/취소: Reservation Agent "
        "handoff 직전에는 반드시 짧게 안내하세요. 예: '예약 담당에게 연결해 드릴게요.' "
        "전문 에이전트가 더 잘 처리할 수 있으면 즉시 handoff 하세요. "
        "중요: 안내 문구만 말하고 끝내지 말고, 반드시 해당 handoff 도구를 실제로 호출하세요."
    ),
    handoffs=[
        handoff(menu_agent),
        handoff(order_agent),
        handoff(reservation_agent),
    ],
)
