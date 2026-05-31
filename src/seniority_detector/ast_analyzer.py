"""Static code metrics extracted from Python AST before sending to the LLM."""

import ast
import re
from dataclasses import dataclass, field


GENERIC_VAR_NAMES: frozenset[str] = frozenset({
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "tmp", "temp", "data", "data2", "data3", "val", "var", "obj",
    "res", "ret", "result2", "foo", "bar", "baz", "stuff", "thing",
})

HARDCODED_PATTERNS: tuple[str, ...] = (
    r'(?<!["\'])https?://[^\s"\']+',
    r'\b(?:localhost|127\.0\.0\.1)\b',
    r'\b\d{4,}\b',
    r'["\'][A-Za-z0-9+/]{20,}={0,2}["\']',
    r'password\s*=\s*["\'][^"\']{3,}["\']',
    r'secret\s*=\s*["\'][^"\']{3,}["\']',
)

_MAX_HARDCODED_MATCHES_PER_PATTERN = 3


@dataclass
class CodeMetrics:
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0

    total_functions: int = 0
    functions_with_docstrings: int = 0
    functions_with_type_hints: int = 0
    functions_over_20_lines: int = 0
    functions_over_50_lines: int = 0
    longest_function_lines: int = 0

    generic_var_names: list[str] = field(default_factory=list)
    total_assignments: int = 0

    try_except_blocks: int = 0
    bare_excepts: int = 0
    except_exception_generic: int = 0

    print_calls: int = 0
    logging_calls: int = 0
    context_managers: int = 0
    list_comprehensions: int = 0
    hardcoded_hints: list[str] = field(default_factory=list)

    total_classes: int = 0
    classes_with_docstrings: int = 0

    cyclomatic_complexity_estimate: int = 0


def _has_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Return True if the first statement of a function or class is a string literal."""
    return (
        bool(node.body)
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


def _count_cyclomatic(tree: ast.AST) -> int:
    """Count branch points as a rough cyclomatic complexity estimate."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                              ast.With, ast.Assert, ast.comprehension)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
    return count


def _function_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the number of lines spanned by a function body."""
    if not node.body:
        return 0
    first_line = node.body[0].lineno
    last_line = node.body[-1].end_lineno or node.body[-1].lineno
    return last_line - first_line + 1


def _scan_hardcoded_hints(source: str) -> list[str]:
    """Return a sample of potentially hardcoded values found in the raw source."""
    hints: list[str] = []
    for pattern in HARDCODED_PATTERNS:
        matches = re.findall(pattern, source, re.IGNORECASE)
        hints.extend(matches[:_MAX_HARDCODED_MATCHES_PER_PATTERN])
    return hints


def analyze(source: str) -> CodeMetrics:
    """Parse Python source and extract measurable quality metrics via AST.

    Returns a CodeMetrics instance populated with counts and signals.
    Falls back gracefully on SyntaxError, returning line-level stats only.
    """
    metrics = CodeMetrics()

    lines = source.splitlines()
    metrics.total_lines = len(lines)
    metrics.blank_lines = sum(1 for line in lines if not line.strip())
    metrics.comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
    metrics.hardcoded_hints = _scan_hardcoded_hints(source)

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return metrics

    metrics.cyclomatic_complexity_estimate = _count_cyclomatic(tree)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics.total_functions += 1
            if _has_docstring(node):
                metrics.functions_with_docstrings += 1
            if bool(node.returns) or any(arg.annotation for arg in node.args.args):
                metrics.functions_with_type_hints += 1
            length = _function_line_count(node)
            metrics.longest_function_lines = max(metrics.longest_function_lines, length)
            if length > 20:
                metrics.functions_over_20_lines += 1
            if length > 50:
                metrics.functions_over_50_lines += 1

        elif isinstance(node, ast.ClassDef):
            metrics.total_classes += 1
            if _has_docstring(node):
                metrics.classes_with_docstrings += 1

        elif isinstance(node, ast.Assign):
            metrics.total_assignments += 1
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in GENERIC_VAR_NAMES:
                    metrics.generic_var_names.append(f"{target.id} (linea {target.lineno})")

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in GENERIC_VAR_NAMES:
                metrics.generic_var_names.append(f"{node.target.id} (linea {node.target.lineno})")

        elif isinstance(node, ast.Try):
            metrics.try_except_blocks += 1
            for handler in node.handlers:
                if handler.type is None:
                    metrics.bare_excepts += 1
                elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                    metrics.except_exception_generic += 1

        elif isinstance(node, ast.With):
            metrics.context_managers += 1

        elif isinstance(node, ast.ListComp):
            metrics.list_comprehensions += 1

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                metrics.print_calls += 1
            elif isinstance(node.func, ast.Attribute):
                is_logging_module = (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logging"
                )
                is_logger_method = node.func.attr in (
                    "debug", "info", "warning", "error", "critical"
                )
                if is_logging_module or is_logger_method:
                    metrics.logging_calls += 1

    return metrics


def metrics_to_summary(metrics: CodeMetrics) -> str:
    """Render metrics as a plain-text block suitable for inclusion in an LLM prompt."""
    doc_pct = (
        round(metrics.functions_with_docstrings / metrics.total_functions * 100)
        if metrics.total_functions else 0
    )
    hint_pct = (
        round(metrics.functions_with_type_hints / metrics.total_functions * 100)
        if metrics.total_functions else 0
    )

    lines = [
        f"Lineas totales: {metrics.total_lines}",
        f"Funciones: {metrics.total_functions} (con docstrings: {doc_pct}%, con type hints: {hint_pct}%)",
        f"Clases: {metrics.total_classes}",
        f"Funcion mas larga: {metrics.longest_function_lines} lineas",
        f"Funciones >20 lineas: {metrics.functions_over_20_lines}",
        f"Funciones >50 lineas: {metrics.functions_over_50_lines}",
        f"Complejidad ciclomatica estimada: {metrics.cyclomatic_complexity_estimate}",
        "",
        f"Variables con nombres genericos: {len(metrics.generic_var_names)}",
    ]
    if metrics.generic_var_names:
        lines.append("  -> " + ", ".join(metrics.generic_var_names[:10]))

    lines += [
        "",
        f"Bloques try/except: {metrics.try_except_blocks}",
        f"  bare except: {metrics.bare_excepts}",
        f"  except Exception generico: {metrics.except_exception_generic}",
        "",
        f"print() para debug: {metrics.print_calls}",
        f"logging calls: {metrics.logging_calls}",
        f"Context managers (with): {metrics.context_managers}",
        f"List comprehensions: {metrics.list_comprehensions}",
    ]

    if metrics.hardcoded_hints:
        lines.append(f"\nPosibles valores hardcodeados detectados: {len(metrics.hardcoded_hints)}")

    return "\n".join(lines)
