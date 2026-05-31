# ¿Eres junior o senior? La IA leyó tu código y dice la verdad

Herramienta CLI que analiza código Python y determina el nivel del desarrollador usando análisis estático (AST + Pylint) combinado con un LLM.

```
Nivel:   SENIOR-
Score:   [#################...] 85/100
Pylint:  W:1  C:3
```

## Cómo funciona

El análisis pasa por tres capas antes de llegar al LLM:

1. **AST** — extrae métricas estructurales: longitud de funciones, presencia de type hints, docstrings, variables genéricas, uso de `print()` vs `logging`, etc.
2. **Pylint** — hallazgos determinísticos con número de línea exacto: `broad-exception-caught`, `missing-docstring`, `consider-using-with`, etc.
3. **LLM** — recibe el código + métricas + hallazgos y devuelve nivel, puntaje, señales concretas y recomendaciones.

## Instalación

Requiere [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/AndresInsuasty/ia-junior-senior.git
cd ia-junior-senior
uv sync
```

Copia el archivo de ejemplo y agrega tu API key:

```bash
cp .env.example .env
# edita .env y agrega OPENAI_API_KEY o ANTHROPIC_API_KEY
```

## Uso

```bash
# Analizar archivo local
uv run python detector.py mi_codigo.py

# Analizar directamente desde GitHub
uv run python detector.py https://github.com/usuario/repo/blob/main/archivo.py

# Ver métricas AST y Pylint completas
uv run python detector.py mi_codigo.py --metricas

# Elegir modelo
uv run python detector.py mi_codigo.py --modelo gpt-4o
uv run python detector.py mi_codigo.py --modelo claude-sonnet-4-6

# Salida JSON (para integrar con otras herramientas)
uv run python detector.py mi_codigo.py --json
```

## Modelos soportados

| Provider   | Modelos                              | Key requerida        |
|------------|--------------------------------------|----------------------|
| OpenAI     | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` | `OPENAI_API_KEY`     |
| Anthropic  | `claude-sonnet-4-6`, `claude-opus-4-8`  | `ANTHROPIC_API_KEY`  |

Si tienes ambas keys, prioriza Anthropic. Si solo tienes una, la detecta automáticamente.

## Ejemplo de salida JSON

```json
{
  "nivel": "junior+",
  "puntaje": 42,
  "señales_junior": [
    "3 funciones sin docstrings",
    "variable 'x' sin contexto en línea 14",
    "except Exception genérico en línea 32"
  ],
  "señales_senior": [
    "type hints en todas las funciones",
    "uso correcto de context managers"
  ],
  "recomendacion": "Prioriza agregar docstrings a todas las funciones...",
  "lineas_a_mejorar": [
    "línea 32: reemplazar 'except Exception' por excepciones específicas"
  ]
}
```

## Niveles

| Nivel     | Descripción                                          |
|-----------|------------------------------------------------------|
| `junior`  | Código funcional con múltiples problemas de calidad  |
| `junior+` | Mejoras visibles pero faltan prácticas clave          |
| `senior-` | Código sólido con algunas áreas de mejora            |
| `senior`  | Código de producción con todas las mejores prácticas |

## Estructura del proyecto

```
detector.py        # CLI principal
ast_analyzer.py    # Métricas estructurales vía AST de Python
pylint_runner.py   # Análisis estático determinístico con Pylint
llm_analyzer.py    # Cliente unificado OpenAI / Anthropic
github_fetcher.py  # Descarga código desde URLs de GitHub
ejemplos/
  codigo_junior.py
  codigo_senior.py
```
