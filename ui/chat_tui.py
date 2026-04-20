from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static, Header, Footer, Input, RichLog, TabbedContent, TabPane

from core.agent import Agent
from core.provider import ModelProvider

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: Optional[str]
    provider: ModelProvider


class StatusBar(Static):
    """Simple status line."""

    status_text = reactive("ready")
    provider_text = reactive("unknown")
    session_text = reactive("new")

    def render(self) -> str:
        return f"provider: {self.provider_text} | session: {self.session_text} | status: {self.status_text}"


class InspectorPanel(TabbedContent):
    """Right-side inspector tabs."""

    def compose(self) -> ComposeResult:
        with TabPane("Session", id="session-tab"):
            yield Static("Session info will appear here.", id="session-info")
        with TabPane("Tools", id="tools-tab"):
            yield Static("Last tool calls / summaries will appear here.", id="tools-info")
        with TabPane("Trading", id="trading-tab"):
            yield Static("Last symbol / regime / action / reason will appear here.", id="trading-info")
        with TabPane("Logs", id="logs-tab"):
            yield Static("Recent warnings/errors will appear here.", id="logs-info")


class ChatTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #main-row {
        height: 1fr;
    }

    #chat-pane {
        width: 2fr;
        border: solid $accent;
    }

    #inspector-pane {
        width: 1fr;
        border: solid $accent;
    }

    #input-row {
        height: 3;
    }

    #prompt-input {
        width: 1fr;
    }

    #status-bar {
        height: 1;
        background: $surface;
        color: $text;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+k", "clear_chat", "Clear Chat"),
        ("ctrl+l", "focus_input", "Focus Input"),
        ("f1", "show_help", "Help"),
    ]

    def __init__(self, session_id: Optional[str], provider: ModelProvider):
        super().__init__()
        self.session_info = SessionInfo(session_id=session_id, provider=provider)
        self.agent: Optional[Agent] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusBar(id="status-bar")

        with Horizontal(id="main-row"):
            with Vertical(id="chat-pane"):
                yield RichLog(id="chat-log", wrap=True, markup=True, highlight=True)
            with Vertical(id="inspector-pane"):
                yield InspectorPanel()

        with Container(id="input-row"):
            yield Input(placeholder="Type a message or /help", id="prompt-input")

        yield Footer()

    def on_mount(self) -> None:
        self.agent = Agent(provider=self.session_info.provider, sid=self.session_info.session_id)
        status = self.query_one(StatusBar)
        status.provider_text = self.session_info.provider.value
        status.session_text = self.agent.sid if getattr(self.agent, "sid", None) else "new"
        status.status_text = "ready"

        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("[bold cyan]AI Trading Agent TUI[/bold cyan]")
        chat_log.write(f"[dim]Provider: {self.session_info.provider.value}[/dim]")
        chat_log.write("[dim]Type /help for commands[/dim]")

        self._update_session_tab()
        self.query_one("#prompt-input", Input).focus()

    def _update_session_tab(self) -> None:
        session_widget = self.query_one("#session-info", Static)
        sid = getattr(self.agent, "sid", None) if self.agent else self.session_info.session_id
        session_widget.update(
            "\n".join(
                [
                    f"Session ID: {sid or 'new'}",
                    f"Provider: {self.session_info.provider.value}",
                    "Mode: tui",
                ]
            )
        )

    def _append_chat(self, speaker: str, text: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if speaker == "user":
            chat_log.write(f"[bold green]You:[/bold green] {text}")
        elif speaker == "agent":
            chat_log.write(f"[bold cyan]Agent:[/bold cyan] {text}")
        elif speaker == "system":
            chat_log.write(f"[yellow]System:[/yellow] {text}")
        else:
            chat_log.write(text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        if text.startswith("/"):
            await self._handle_command(text)
            return

        self._append_chat("user", text)
        await self._run_agent_chat(text)

    async def _handle_command(self, text: str) -> None:
        command = text.strip().lower()

        if command == "/help":
            self._append_chat("system", "Commands: /help /clear /reset /status")
        elif command == "/clear":
            self.action_clear_chat()
        elif command == "/status":
            self._append_chat(
                "system",
                f"provider={self.session_info.provider.value} session={getattr(self.agent, 'sid', 'unknown')}",
            )
        elif command == "/reset":
            self.agent = Agent(provider=self.session_info.provider, sid=None)
            self._append_chat("system", "Agent session reset.")
            self._update_session_tab()
        else:
            self._append_chat("system", f"Unknown command: {command}")

    async def _run_agent_chat(self, text: str) -> None:
        status = self.query_one(StatusBar)
        status.status_text = "thinking"

        try:
            response = await asyncio.to_thread(self.agent.chat, text)
            if not response:
                response = "(no response)"
            self._append_chat("agent", str(response))
        except Exception as e:
            logger.exception("TUI agent.chat failed")
            self._append_chat("system", f"Error: {e}")
        finally:
            status.status_text = "ready"

    def action_clear_chat(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        self._append_chat("system", "Chat cleared.")

    def action_focus_input(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_show_help(self) -> None:
        self._append_chat("system", "F1 Help | Ctrl+K Clear | Ctrl+L Focus Input | Ctrl+C Quit")


def run_tui(session_id: Optional[str], provider: ModelProvider) -> None:
    app = ChatTUI(session_id=session_id, provider=provider)
    app.run()
