"""
AI Crypto Trading Agent - Console Interface

This script provides a direct console interface to chat with the AI Agent.
It can also be used to launch the Telegram bot.
"""

import logging
import os
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console

# Add current directory to path to ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import run_loop
from core.provider import ModelProvider, get_provider

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler(sys.stdout) if "--debug" in sys.argv else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="agent",
    help="AI Crypto Trading Agent CLI",
)

console = Console()


@app.command()
def login():
    """Authenticate and configure your LLM Provider."""
    from core.auth import interactive_login
    interactive_login()


@app.command()
def chat(
    session_id: str = typer.Option(None, "--session", "-s", help="Resume a specific session ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="Model provider (anthropic, ollama, gemini, openai, openai-codex)"),
) -> None:
    """Start an interactive console chat with the AI Trading Agent."""
    
    # Resolve provider
    model_provider = None
    if provider:
        try:
            model_provider = ModelProvider(provider.lower())
        except ValueError:
            console.print(f"[red]Error:[/] Invalid provider '{provider}'. Choose from: anthropic, ollama, gemini, openai, openai-codex")
            raise typer.Exit(code=1)
    
    if model_provider is None:
        model_provider = get_provider()

    # Check for API keys if needed
    if model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            console.print(
                "[red]Error: ANTHROPIC_API_KEY is not set.[/red]\n"
                "Please run 'python3 agent.py login' or add your API key to the .env file."
            )
            raise typer.Exit(code=1)
    elif model_provider == ModelProvider.GEMINI:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        token_path = os.path.expanduser("~/.agent_google_token.json")
        if not api_key and not os.path.exists(token_path):
            console.print(
                "[red]Error: No Gemini authentication found.[/red]\n"
                "Please run 'python3 agent.py login' to link your Google Account or add an API key."
            )
            raise typer.Exit(code=1)
    elif model_provider == ModelProvider.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            console.print(
                "[red]Error: OPENAI_API_KEY is not set.[/red]\n"
                "Please run 'python3 agent.py login' or add your API key to the .env file."
            )
            raise typer.Exit(code=1)
    elif model_provider == ModelProvider.OPENAI_CODEX:
        token_path = os.path.expanduser(os.getenv("OPENAI_CODEX_TOKEN_PATH", "~/.agent_openai_codex_auth.json"))
        if not os.path.exists(token_path):
            console.print(
                "[red]Error: OpenAI Codex OAuth token is not set.[/red]\n"
                "Please run 'python3 agent.py login' and choose OpenAI ChatGPT/Codex Web Auth."
            )
            raise typer.Exit(code=1)

    console.print(f"[bold cyan]AI Trading Agent[/bold cyan] — [bold white]{model_provider.value}[/] provider\n")
    console.print("[dim]Interface: Console REPL[/dim]")
    
    try:
        run_loop(sid=session_id, provider=model_provider)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        logger.exception("Error in console chat loop")
        raise typer.Exit(code=1)


@app.command()
def bot(
    provider: str = typer.Option(None, "--provider", "-p", help="Model provider"),
) -> None:
    """Start the Telegram bot interface."""
    
    model_provider = None
    if provider:
        try:
            model_provider = ModelProvider(provider.lower())
        except ValueError:
            console.print(f"[red]Error:[/] Invalid provider '{provider}'.")
            raise typer.Exit(code=1)
            
    if model_provider is None:
        model_provider = get_provider()

    console.print(f"[bold cyan]Telegram Bot Interface[/bold cyan] — [bold white]{model_provider.value}[/] provider\n")
    
    try:
        from core.telegram_bot import TelegramBot
        bot_instance = TelegramBot(provider=model_provider)
        console.print("[bold green]🚀 Telegram bot is active![/bold green]")
        console.print("[yellow]Press Ctrl+C to shut down.[/yellow]")
        bot_instance.run()
    except Exception as e:
        console.print(f"[bold red]Fatal Error:[/] {e}")
        logger.exception("Error launching Telegram bot")
        raise typer.Exit(code=1)


@app.command()
def tui(
    session_id: str = typer.Option(None, "--session", "-s", help="Resume a specific session ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="Model provider (anthropic, ollama, gemini, openai, openai-codex)"),
) -> None:
    """Start the Textual TUI interface."""
    model_provider = None
    if provider:
        try:
            model_provider = ModelProvider(provider.lower())
        except ValueError:
            console.print(f"[red]Error:[/] Invalid provider '{provider}'. Choose from: anthropic, ollama, gemini, openai, openai-codex")
            raise typer.Exit(code=1)

    if model_provider is None:
        model_provider = get_provider()

    try:
        from ui.chat_tui_v2 import run_tui
        run_tui(session_id=session_id, provider=model_provider)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        logger.exception("Error in TUI")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
