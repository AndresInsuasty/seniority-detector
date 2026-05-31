"""Unified LLM analyzer — routes to OpenAI or Anthropic based on model name."""

import json
import os
import re

from ast_analyzer import CodeMetrics, metrics_to_summary


MAX_CODE_CHARS: int = 4_000
ENV_KEY_OPENAI = "OPENAI_API_KEY"
ENV_KEY_ANTHROPIC = "ANTHROPIC_API_KEY"

SYSTEM_PROMPT = """Eres un experto en calidad de código Python con 15 años de experiencia revisando código en empresas de tecnología de primer nivel.

Tu tarea es analizar código Python y determinar el nivel del desarrollador basándote en señales concretas y medibles.

**Niveles posibles:**
- junior: código funcional pero con múltiples problemas de calidad
- junior+: mejoras visibles pero aún faltan prácticas clave
- senior-: código sólido con algunas áreas de mejora
- senior: código de producción con todas las mejores prácticas

**Señales junior (restan puntos):**
- Variables genéricas: a, b, x, temp, data2
- Sin manejo de errores o except genérico
- Funciones largas que hacen múltiples cosas
- Sin docstrings ni type hints
- print() para debug en lugar de logging
- Valores hardcodeados (contraseñas, URLs, magic numbers)
- Loops donde caben list comprehensions

**Señales senior (suman puntos):**
- Nombres descriptivos y autoexplicativos
- Type hints completos
- Docstrings con descripción y parámetros
- Context managers para recursos
- Excepciones específicas con mensajes útiles
- Configuración separada del código
- Funciones pequeñas con una responsabilidad
- Logging estructurado

Responde ÚNICAMENTE con un JSON válido, sin texto adicional, sin bloques de código markdown."""

USER_TEMPLATE = """Analiza este código Python:

--- MÉTRICAS AST CALCULADAS ---
{metrics}

--- HALLAZGOS PYLINT (determinísticos, con número de línea exacto) ---
{pylint}

--- CÓDIGO FUENTE ---
```python
{code}
```

Responde con este JSON exacto:
{{
  "nivel": "junior|junior+|senior-|senior",
  "puntaje": <número entre 0 y 100>,
  "señales_junior": [<lista de strings con señales negativas encontradas>],
  "señales_senior": [<lista de strings con señales positivas encontradas>],
  "recomendacion": "<párrafo concreto con los 2-3 cambios más importantes que debería hacer>",
  "lineas_a_mejorar": [<lista de strings con ejemplos específicos del código, máximo 5>]
}}"""


def is_openai_model(model: str) -> bool:
    """Return True if the model name belongs to the OpenAI family."""
    return model.startswith(("gpt", "o1", "o3"))


def default_model() -> str:
    """Return the best available model based on environment keys.

    Raises:
        EnvironmentError: If neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set.
    """
    if os.environ.get(ENV_KEY_ANTHROPIC):
        return "claude-sonnet-4-6"
    if os.environ.get(ENV_KEY_OPENAI):
        return "gpt-5-mini"
    raise EnvironmentError(
        "No se encontró ninguna API key. "
        "Define OPENAI_API_KEY o ANTHROPIC_API_KEY en tu entorno o en un archivo .env."
    )


def _truncate_source(source: str) -> str:
    """Cap source code length to avoid excessive API costs."""
    if len(source) <= MAX_CODE_CHARS:
        return source
    return source[:MAX_CODE_CHARS] + "\n... [truncado]"


def _parse_response(raw: str) -> dict:
    """Extract a JSON dict from the raw LLM response, stripping any markdown fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"El modelo no devolvio JSON valido:\n{raw[:300]}")


def _build_user_message(source: str, metrics: CodeMetrics, pylint_summary: str) -> str:
    """Assemble the user-turn prompt from source, AST metrics, and pylint findings."""
    return USER_TEMPLATE.format(
        metrics=metrics_to_summary(metrics),
        pylint=pylint_summary,
        code=_truncate_source(source),
    )


def _openai_client():
    """Build an OpenAI client that trusts the system's native TLS certificate store."""
    import ssl
    import httpx
    from openai import OpenAI

    ssl_context = ssl.create_default_context()
    return OpenAI(
        api_key=os.environ[ENV_KEY_OPENAI],
        http_client=httpx.Client(verify=ssl_context),
    )


def _analyze_openai(source: str, metrics: CodeMetrics, pylint_summary: str, model: str) -> dict:
    """Send source, AST metrics, and pylint findings to an OpenAI model and return parsed analysis."""
    client = _openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(source, metrics, pylint_summary)},
        ],
    )
    choice = response.choices[0]
    content = choice.message.content
    if not content:
        raise ValueError(
            f"El modelo devolvio contenido vacio (finish_reason: {choice.finish_reason})"
        )
    return _parse_response(content)


def _analyze_anthropic(source: str, metrics: CodeMetrics, pylint_summary: str, model: str) -> dict:
    """Send source, AST metrics, and pylint findings to an Anthropic model and return parsed analysis."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ[ENV_KEY_ANTHROPIC])
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _build_user_message(source, metrics, pylint_summary)}],
    )
    return _parse_response(response.content[0].text)


def analyze(source: str, metrics: CodeMetrics, pylint_summary: str, model: str) -> dict:
    """Route to the correct provider and return the analysis dict.

    Args:
        source: Raw Python source code.
        metrics: Pre-computed AST metrics.
        pylint_summary: Pre-formatted pylint findings string (may be empty).
        model: Model identifier, used to select the provider.
    """
    if is_openai_model(model):
        return _analyze_openai(source, metrics, pylint_summary, model)
    return _analyze_anthropic(source, metrics, pylint_summary, model)
