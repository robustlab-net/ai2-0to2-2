from __future__ import annotations

from agents import GuardrailFunctionOutput, input_guardrail, output_guardrail

BLOCKED_INPUT_KEYWORDS = (
    "자살",
    "자해",
    "폭탄",
    "마약",
    "해킹",
    "총 만드는",
    "칼 만드는",
)

OFF_TOPIC_KEYWORDS = (
    "주식",
    "코딩 과제",
    "정치 뉴스",
    "부동산",
    "의료 진단",
)

SENSITIVE_OUTPUT_MARKERS = (
    "api key",
    "secret",
    "system prompt",
    "developer message",
)


def _normalize_input(user_input: str | list[object]) -> str:
    if isinstance(user_input, str):
        return user_input.strip().lower()
    return str(user_input).strip().lower()


@input_guardrail(name="restaurant_domain_input_guardrail", run_in_parallel=False)
def restaurant_domain_input_guardrail(
    ctx, agent, user_input: str | list[object]
) -> GuardrailFunctionOutput:
    normalized = _normalize_input(user_input)

    if any(keyword in normalized for keyword in BLOCKED_INPUT_KEYWORDS):
        return GuardrailFunctionOutput(
            output_info="안전하지 않은 요청이 감지되어 차단했습니다.",
            tripwire_triggered=True,
        )

    if any(keyword in normalized for keyword in OFF_TOPIC_KEYWORDS):
        return GuardrailFunctionOutput(
            output_info="레스토랑 운영 범위를 벗어난 요청이라 처리할 수 없습니다.",
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info="ok",
        tripwire_triggered=False,
    )


@output_guardrail(name="restaurant_output_guardrail")
def restaurant_output_guardrail(
    ctx, agent, agent_output: object
) -> GuardrailFunctionOutput:
    text = str(agent_output).strip().lower()

    if any(marker in text for marker in SENSITIVE_OUTPUT_MARKERS):
        return GuardrailFunctionOutput(
            output_info="민감한 내부 정보 노출 가능성이 있어 응답을 차단했습니다.",
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info="ok",
        tripwire_triggered=False,
    )
