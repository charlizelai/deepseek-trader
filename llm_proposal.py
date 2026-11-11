"""
DeepSeek proposal layer. The model outputs ONLY a structured TradeIntent via
strict function calling -- side / symbol / confidence / reason. It has no
field for position size, so it can never propose an oversized order.
"""
import json
import logging

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL, SYMBOL

log = logging.getLogger("trader")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

TRADE_INTENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_trade_intent",
        "description": "Submit a trading intent. The system will decide position size and risk.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "side": {"type": "string", "enum": ["buy", "sell", "hold"], "description": "Trade direction"},
                "symbol": {"type": "string", "enum": [SYMBOL], "description": "Trading pair"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Model confidence in the signal"},
                "reason": {"type": "string", "maxLength": 200, "description": "Brief rationale for the intent"},
            },
            "required": ["side", "symbol", "confidence", "reason"],
            "additionalProperties": False,
        },
    },
}


def get_trade_intent(market_snapshot: dict) -> dict:
    """Return the TradeIntent arguments dict from DeepSeek."""
    prompt = f"""
You are a conservative crypto trading analyst. Based on the market snapshot below,
decide whether to buy, sell, or hold {SYMBOL}.

Market snapshot:
{json.dumps(market_snapshot, indent=2)}

Only submit a trade intent if you have a clear directional signal.
When uncertain, submit "hold".
Do NOT suggest position sizes -- that is handled elsewhere.
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        tools=[TRADE_INTENT_SCHEMA],
        tool_choice={"type": "function", "function": {"name": "submit_trade_intent"}},
        extra_body={"thinking": {"type": "disabled"}},
    )
    message = response.choices[0].message
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments)
    # Fail-safe fallback: no tool call returned -> treat as hold
    return {"side": "hold", "symbol": SYMBOL, "confidence": 0.0, "reason": "no tool call returned"}
