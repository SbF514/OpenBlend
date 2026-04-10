"""OpenBlend Public CLI — Pre-trained blended LLM. 🍸

Commands:
  openblend serve    — Start the OpenBlend API server
  openblend status   — Show active providers and ELO summary
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="openblend",
    help="🍸 OpenBlend Public — Pre-trained blended LLM outperforms any single model",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-H", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Auto-reload on changes"),
) -> None:
    """Start the OpenBlend API server (OpenAI-compatible at localhost:8000)."""
    import uvicorn

    console.print(Panel.fit(
        "[bold magenta]🍸 OpenBlend Server[/bold magenta]\n"
        f"Listening on [cyan]http://{host}:{port}[/cyan]\n"
        "POST /v1/chat/completions • GET /health • GET /v1/models",
        border_style="magenta",
    ))
    uvicorn.run(
        "openblend_public.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def status() -> None:
    """Show active providers and ELO summary."""
    from openblend_public.config import get_config
    from openblend_public.memory.store import get_rankings, get_all_categories

    cfg = get_config()
    slots = cfg.all_slots()

    # Provider table
    table = Table(title="🍸 Active Providers", show_lines=True, border_style="dim")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Model", style="white")
    table.add_column("Transport", style="yellow")
    table.add_column("Tier", style="magenta")
    table.add_column("Cost (out)", justify="right", style="green")

    for slot in slots:
        table.add_row(
            slot.provider,
            slot.model,
            slot.transport.value.upper(),
            slot.tier.value,
            f"${slot.cost_output:.4f}" if slot.cost_output > 0 else "FREE",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(slots)} slots from {len(cfg.active_providers)} providers[/dim]")

    # ELO summary
    categories = get_all_categories()
    if categories:
        console.print()
        elo_table = Table(title="🏆 ELO Rankings", show_lines=True, border_style="dim")
        elo_table.add_column("Category", style="cyan")
        elo_table.add_column("#1 Provider", style="green")
        elo_table.add_column("ELO", justify="right", style="yellow")
        elo_table.add_column("Win Rate", justify="right", style="magenta")

        for cat in sorted(categories):
            rankings = get_rankings(cat)
            if rankings:
                top = rankings[0]
                total = top["total"]
                rate = f"{top['wins']/total*100:.0f}%" if total > 0 else "N/A"
                elo_table.add_row(cat, f"{top['provider']}/{top['model']}", f"{top['elo']:.0f}", rate)

        console.print(elo_table)

    else:
        console.print("\n[dim]No ELO data loaded.[/dim]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
