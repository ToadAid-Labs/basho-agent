from typing import Any

from rich.console import Console
from rich.markdown import Markdown

from core.agent import Agent
from core.provider import ModelProvider, get_provider

console = Console()

MAX_ITERATIONS = 50


def run_loop(sid: str | None = None, provider: ModelProvider | None = None) -> None:
    """Main interactive REPL loop."""
    if provider is None:
        provider = get_provider()

    agent = Agent(provider=provider, sid=sid)

    console.print(
        "[bold green]Agent ready![/bold green] "
        "Type your task, or 'exit' to quit. Using tools automatically.\n"
    )

    iteration = 0
    while iteration < MAX_ITERATIONS:
        try:
            user_input = console.input("[bold blue]> [/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        response_text = agent.chat(user_input)

        if response_text:
            console.print()
            console.print(Markdown(response_text))

        iteration += 1

    if iteration >= MAX_ITERATIONS:
        console.print(
            f"[yellow]Max iterations ({MAX_ITERATIONS}) reached. Ending session.[/yellow]"
        )
