"""Tabla de precios de lista (USD por millón de tokens) y cálculo de costo.
Compartida por los collectors que estiman costo (claude_code, codex).
OpenCode no usa este módulo porque ya reporta su propio costo calculado.
"""

PRICING = {
    "claude-opus-5":             {"in": 15.0, "out": 75.0, "cache_r": 1.5, "cache_w": 18.75},
    "claude-sonnet-5":           {"in": 3.0,  "out": 15.0, "cache_r": 0.3, "cache_w": 3.75},
    "claude-haiku-4-5-20251001": {"in": 1.0,  "out": 5.0,  "cache_r": 0.1, "cache_w": 1.25},
    "claude-fable-5":            {"in": 3.0,  "out": 15.0, "cache_r": 0.3, "cache_w": 3.75},
    # Modelos OpenAI vistos en Codex (precios de lista aproximados, ajustar si cambian)
    "gpt-5.5":                   {"in": 2.5,  "out": 10.0, "cache_r": 0.25, "cache_w": 2.5},
    "gpt-5.5-fast":              {"in": 2.5,  "out": 10.0, "cache_r": 0.25, "cache_w": 2.5},
    "gpt-5.5-mini":              {"in": 0.5,  "out": 2.0,  "cache_r": 0.05, "cache_w": 0.5},
}
DEFAULT_PRICE = None  # sin default silencioso: modelo desconocido -> costo None


def price_for(model):
    if not model:
        return None
    for key, p in PRICING.items():
        if key in model:
            return p
    return None


def cost_of(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model):
    p = price_for(model)
    if p is None:
        return None
    return (
        (input_tokens or 0) * p["in"]
        + (output_tokens or 0) * p["out"]
        + (cache_read_tokens or 0) * p["cache_r"]
        + (cache_write_tokens or 0) * p["cache_w"]
    ) / 1_000_000
