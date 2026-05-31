#!/usr/bin/env python3
"""
cli.py — Analiza código Python y determina si es de nivel junior o senior.

Uso:
    detector mi_codigo.py
    detector https://github.com/usuario/repo/blob/main/archivo.py
    detector mi_codigo.py --modelo gpt-4o
    detector mi_codigo.py --modelo claude-sonnet-4-6
    detector mi_codigo.py --json
"""

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from .ast_analyzer import analyze as ast_analyze, metrics_to_summary
from .github_fetcher import fetch_github_source
from .llm_analyzer import (
    analyze as llm_analyze,
    default_model,
    is_openai_model,
    ENV_KEY_OPENAI,
    ENV_KEY_ANTHROPIC,
)
from .pylint_runner import run_pylint, pylint_to_summary, pylint_counts

load_dotenv()

app = typer.Typer(add_completion=False)
console = Console()

NIVEL_COLORS: dict[str, str] = {
    "junior": "red",
    "junior+": "yellow",
    "senior-": "cyan",
    "senior": "green",
}


def _score_bar(score: int) -> str:
    """Render a fixed-width ASCII progress bar for a 0–100 score."""
    filled = round(score / 5)
    empty = 20 - filled
    return f"[{'#' * filled}{'.' * empty}] {score}/100"


def _load_source(input_path: str) -> tuple[str, str]:
    """Return (source_code, filename) from a local path or GitHub URL.

    Raises:
        FileNotFoundError: If the local file does not exist.
        ValueError: If a GitHub URL format is not recognised.
        requests.HTTPError: If the GitHub download fails.
    """
    if input_path.startswith(("http://", "https://")):
        return fetch_github_source(input_path)

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {input_path}")
    return path.read_text(encoding="utf-8"), path.name


def _required_env_key(model: str) -> str:
    """Return the environment variable name required for the given model."""
    return ENV_KEY_OPENAI if is_openai_model(model) else ENV_KEY_ANTHROPIC


def _check_api_key(model: str) -> None:
    """Exit with a friendly message if the required API key is missing.

    Raises:
        typer.Exit: Always raised when a key is missing.
    """
    env_var = _required_env_key(model)
    if not os.environ.get(env_var):
        console.print(
            Panel(
                f"Falta [bold]{env_var}[/] en el entorno.\n\n"
                f"Crea un archivo [dim].env[/] con:\n"
                f"  [dim]{env_var}=...[/]",
                title="[red]API Key no encontrada[/]",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def _render_pylint_counts(counts: dict[str, int]) -> str:
    """Format pylint category counts as a compact inline string, e.g. 'E:2  W:5  C:10'."""
    parts = [
        f"{category[0].upper()}:{count}"
        for category in ("fatal", "error", "warning", "refactor", "convention")
        if (count := counts.get(category, 0))
    ]
    return "  ".join(parts) if parts else "sin hallazgos"


def _build_header_panel(result: dict, filename: str, pylint_counts_by_type: dict[str, int]) -> Panel:
    """Build the top summary panel with file, level, score, and pylint counts."""
    nivel = result.get("nivel", "desconocido")
    score = result.get("puntaje", 0)
    color = NIVEL_COLORS.get(nivel, "white")

    header = Text()
    header.append("\n  Archivo: ", style="dim")
    header.append(filename, style="bold white")
    header.append("\n\n  Nivel:   ", style="dim")
    header.append(nivel.upper(), style=f"bold {color}")
    header.append("\n  Score:   ", style="dim")
    header.append(_score_bar(score), style=color)
    header.append("\n  Pylint:  ", style="dim")
    header.append(_render_pylint_counts(pylint_counts_by_type), style="dim white")
    header.append("\n")

    return Panel(header, title="[bold]Analisis de Codigo[/]", border_style=color, box=box.DOUBLE)


def _build_signals_table(result: dict) -> Table:
    """Build a two-column Rich table with junior vs senior signals from the analysis."""
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    table.add_column("Senales Junior", style="red", ratio=1)
    table.add_column("Senales Senior", style="green", ratio=1)

    junior_signals: list[str] = result.get("señales_junior", [])
    senior_signals: list[str] = result.get("señales_senior", [])
    for i in range(max(len(junior_signals), len(senior_signals), 1)):
        junior_cell = f"• {junior_signals[i]}" if i < len(junior_signals) else ""
        senior_cell = f"• {senior_signals[i]}" if i < len(senior_signals) else ""
        table.add_row(junior_cell, senior_cell)

    return table


def _print_result(result: dict, filename: str, pylint_counts_by_type: dict[str, int]) -> None:
    """Render the full analysis result to the terminal using Rich."""
    console.print(_build_header_panel(result, filename, pylint_counts_by_type))
    console.print(_build_signals_table(result))

    recommendation = result.get("recomendacion", "")
    if recommendation:
        console.print(
            Panel(recommendation, title="[bold yellow]Recomendacion[/]", border_style="yellow", padding=(1, 2))
        )

    improvement_lines: list[str] = result.get("lineas_a_mejorar", [])
    if improvement_lines:
        console.print("\n[bold]Fragmentos a mejorar:[/]")
        for line in improvement_lines:
            console.print(f"  -> {line}")

    console.print()


@app.command()
def main(
    input_path: str = typer.Argument(..., help="Archivo .py local o URL de GitHub"),
    modelo: str = typer.Option(
        None,
        "--modelo", "-m",
        help="Modelo a usar: gpt-4o, gpt-4-turbo, claude-sonnet-4-6, claude-opus-4-8",
    ),
    output_json: bool = typer.Option(False, "--json", "-j", help="Imprimir resultado como JSON"),
    show_metrics: bool = typer.Option(False, "--metricas", help="Mostrar metricas AST calculadas"),
) -> None:
    """Analiza codigo Python y determina si fue escrito por un junior o senior."""
    if modelo is None:
        try:
            modelo = default_model()
        except EnvironmentError as exc:
            console.print(Panel(str(exc), title="[red]Sin API Key[/]", border_style="red"))
            raise typer.Exit(1) from exc

    _check_api_key(modelo)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:
        progress.add_task("Cargando codigo...", total=None)
        try:
            source, filename = _load_source(input_path)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(1) from exc

    metrics = ast_analyze(source)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:
        progress.add_task("Ejecutando pylint...", total=None)
        pylint_messages = run_pylint(source)

    pylint_summary = pylint_to_summary(pylint_messages)
    counts = pylint_counts(pylint_messages)

    if show_metrics:
        console.print(Panel(metrics_to_summary(metrics), title="Metricas AST", border_style="dim"))
        console.print(Panel(pylint_summary, title="Hallazgos Pylint", border_style="dim"))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:
        progress.add_task(f"Consultando {modelo}...", total=None)
        try:
            result = llm_analyze(source, metrics, pylint_summary, model=modelo)
        except (ValueError, KeyError) as exc:
            console.print(f"[red]Error al consultar el modelo:[/] {exc}")
            raise typer.Exit(1) from exc

    if output_json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        _print_result(result, filename, counts)


if __name__ == "__main__":
    app()
