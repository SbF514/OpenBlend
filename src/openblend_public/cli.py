"""OpenBlend CLI — Pre-trained blended LLM. 🍸

Commands:
  openblend serve    — Start the OpenBlend API server
  openblend status   — Show active providers and ELO summary
  openblend init     — Interactive setup wizard for API keys
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

app = typer.Typer(
    name="openblend",
    help="🍸 OpenBlend — Pre-trained blended LLM outperforms any single model",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def init() -> None:
    """Interactive setup wizard — helps you configure API keys easily."""
    from dotenv import load_dotenv

    console.print(Panel.fit(
        "[bold blue]🚀 OpenBlend Interactive Setup[/bold blue]\n\n"
        "This will help you set up your API keys.\n"
        "You need at least one premium API key for judging.\n"
        "We recommend adding free providers for extra candidate generation at no cost.",
        border_style="blue",
    ))

    console.print()
    console.print("[bold]Free provider options you can add:[/bold]")
    console.print("• [cyan]OpenRouter[/cyan] — Many free models available: https://openrouter.ai/")
    console.print("• [cyan]Kilo Gateway[/cyan] — Free tier available: https://kilo.ai/")
    console.print("• [cyan]Google Gemini[/cyan] — Free tier available: https://ai.google.dev/")
    console.print("• [cyan]OpenCodeZen[/cyan] — Free model access: https://opencodezen.com/")
    console.print()

    # Check if .env already exists
    env_path = Path(".") / ".env"
    existing: dict[str, str] = {}
    if env_path.exists():
        load_dotenv(env_path)
        for key in ["BAOSI_API_KEY", "OPENAI_API_KEY", "KILO_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"]:
            val = os.getenv(key)
            if val:
                existing[key] = val
        console.print(f"[yellow]Found existing .env with {len(existing)} API keys already configured.[/yellow]")
        console.print()

    # Premium provider selection
    console.print("[bold]Step 1: Premium Provider (required)[/bold]")
    console.print("You need at least one premium API key for the judge role.")
    provider_choice = Prompt.ask(
        "Which premium provider do you want to use?",
        choices=["anthropic", "openai", "gemini", "other"],
        default="anthropic" if "BAOSI_API_KEY" not in existing else "anthropic"
    )

    api_key: Optional[str] = None
    provider_name: str = ""
    env_var: str = ""
    base_url: str = ""

    if provider_choice == "anthropic":
        provider_name = "Anthropic Claude"
        env_var = "BAOSI_API_KEY"
        base_url = "https://api.anthropic.com/v1"
        default_key = existing.get(env_var, "")
        api_key = Prompt.ask(f"Enter your [bold]{provider_name}[/bold] API key", default=default_key)
    elif provider_choice == "openai":
        provider_name = "OpenAI"
        env_var = "OPENAI_API_KEY"
        base_url = "https://api.openai.com/v1"
        default_key = existing.get(env_var, "")
        api_key = Prompt.ask(f"Enter your [bold]{provider_name}[/bold] API key", default=default_key)
    elif provider_choice == "gemini":
        provider_name = "Google Gemini"
        env_var = "GEMINI_API_KEY"
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        default_key = existing.get(env_var, "")
        api_key = Prompt.ask(f"Enter your [bold]{provider_name}[/bold] API key", default=default_key)
    elif provider_choice == "other":
        provider_name = "Custom"
        env_var = Prompt.ask("Enter environment variable name for API key (e.g. CUSTOM_API_KEY)")
        base_url = Prompt.ask("Enter base URL for this provider")
        default_key = existing.get(env_var, "")
        api_key = Prompt.ask(f"Enter your API key", default=default_key)

    console.print()
    console.print("[bold]Step 2: Free Providers (optional but recommended)[/bold]")
    console.print("Adding free providers gives you more candidate models at no extra cost.")

    free_providers: list[tuple[str, str, str]] = []

    if Confirm.ask("Add Kilo Gateway?", default=True):
        key = Prompt.ask("Enter your KILO_API_KEY", default=existing.get("KILO_API_KEY", ""))
        if key:
            free_providers.append(("KILO_API_KEY", key, "https://api.kilo.ai/api/gateway"))

    if Confirm.ask("Add OpenRouter?", default=True):
        key = Prompt.ask("Enter your OPENROUTER_API_KEY", default=existing.get("OPENROUTER_API_KEY", ""))
        if key:
            free_providers.append(("OPENROUTER_API_KEY", key, "https://openrouter.ai/api/v1"))

    if Confirm.ask("Add Google Gemini (free)?", default=False):
        key = Prompt.ask("Enter your GEMINI_API_KEY", default=existing.get("GEMINI_API_KEY", ""))
        if key and provider_choice != "gemini":
            free_providers.append(("GEMINI_API_KEY", key, "https://generativelanguage.googleapis.com/v1beta/openai/"))

    # Build .env content
    lines: list[str] = []
    lines.append("# OpenBlend Configuration - Generated by openblend init")
    lines.append("")

    # Add premium
    lines.append(f"# {provider_name}")
    lines.append(f"{env_var}={api_key}")
    lines.append("")

    # Add free providers
    if free_providers:
        lines.append("# Free providers for extra candidate generation")
        for name, key, _ in free_providers:
            lines.append(f"{name}={key}")
        lines.append("")

    lines.append("# Add more providers here if needed")

    # Write .env
    content = "\n".join(lines)
    if env_path.exists():
        if not Confirm.ask(".env already exists. Overwrite it?", default=False):
            console.print("[yellow]Aborted - no changes made.[/yellow]")
            return

    with open(env_path, "w") as f:
        f.write(content)

    console.print()
    console.print(Panel.fit(
        "[bold green]✅ Setup complete![/bold green]\n\n"
        f"Config saved to [cyan].env[/cyan]\n"
        "Run [bold]openblend status[/bold] to verify your configuration\n"
        "Then run [bold]openblend serve[/bold] to start the API server!",
        border_style="green",
    ))


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
