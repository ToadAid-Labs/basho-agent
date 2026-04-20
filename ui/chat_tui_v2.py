import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, RichLog, Static, TabbedContent, TabPane

from core.agent import Agent
from core.provider import ModelProvider

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: Optional[str]
    provider: ModelProvider


class TopStatusBar(Static):
    provider_text = reactive("unknown")
    session_text = reactive("new")
    mode_text = reactive("chat")
    state_text = reactive("ready")

    def render(self) -> str:
        return (
            f" provider: {self.provider_text} "
            f"| session: {self.session_text} "
            f"| mode: {self.mode_text} "
            f"| status: {self.state_text} "
        )


class InspectorTabs(TabbedContent):
    def compose(self) -> ComposeResult:
        with TabPane("Session", id="tab-session"):
            yield Static("No session info yet.", id="session-panel")
        with TabPane("Tools", id="tab-tools"):
            yield Static("No tool activity yet.", id="tools-panel")
        with TabPane("Trading", id="tab-trading"):
            yield Static("No trading state yet.", id="trading-panel")
        with TabPane("Logs", id="tab-logs"):
            yield Static("No log events yet.", id="logs-panel")


class ChatTUIv2(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #top-status {
        height: 1;
        background: $surface;
        color: $text;
    }

    #body {
        height: 1fr;
    }

    #left-column {
        width: 1fr;
    }

    #right-column {
        width: 34;
        display: none;
    }

    #chat-log {
        height: 1fr;
        border: round $accent;
    }

    #events-log {
        height: 1fr;
        border: round $accent;
        margin-top: 1;
        display: none;
    }

    #inspector {
        height: 1fr;
        border: round $accent;
    }

    #input-row {
        height: 3;
        margin-top: 1;
    }

    #prompt-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+k", "clear_chat", "Clear Chat"),
        ("ctrl+l", "focus_input", "Focus Input"),
        ("ctrl+r", "retry_last", "Retry"),
        ("f1", "show_help", "Help"),
        ("f2", "toggle_inspector", "Inspector"),
        ("f3", "toggle_events", "Events"),
    ]

    def __init__(self, session_id: Optional[str], provider: ModelProvider) -> None:
        super().__init__()
        self.session_info = SessionInfo(session_id=session_id, provider=provider)
        self.agent: Optional[Agent] = None
        self.last_user_prompt: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TopStatusBar(id="top-status")

        with Horizontal(id="body"):
            with Vertical(id="left-column"):
                yield RichLog(id="chat-log", wrap=True, markup=True, highlight=True)
                yield RichLog(id="events-log", wrap=True, markup=True, highlight=True)
            with Vertical(id="right-column"):
                yield InspectorTabs(id="inspector")

        with Container(id="input-row"):
            yield Input(placeholder="Type a message or /help", id="prompt-input")

        yield Footer()

    def on_mount(self) -> None:
        sid = self.session_info.session_id
        if not sid:
            sid = uuid.uuid4().hex[:12]
        self.agent = Agent(provider=self.session_info.provider, sid=sid)

        status = self.query_one("#top-status", TopStatusBar)
        status.provider_text = self.session_info.provider.value
        status.session_text = getattr(self.agent, "sid", None) or "new"
        status.mode_text = "tui"
        status.state_text = "ready"

        self.chat_log.write("[bold cyan]AI Trading Agent TUI v2[/bold cyan]")
        self.chat_log.write(f"[dim]Provider: {self.session_info.provider.value}[/dim]")
        self.chat_log.write("[dim]Commands: /help /clear /reset /status[/dim]")

        self.event_log.write("[yellow]system[/yellow] TUI started")
        self._update_session_panel()
        self._focus_input()

    @property
    def chat_log(self) -> RichLog:
        return self.query_one("#chat-log", RichLog)

    @property
    def event_log(self) -> RichLog:
        return self.query_one("#events-log", RichLog)

    def _focus_input(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _normalize_chat_text_for_display(self, text: str) -> str:
        """Normalize agent response for display, collapsing pathological newlines while preserving paragraphs and lists."""
        if not text:
            return ""
            
        # 1. Normalize pathological single newlines (convert to space)
        # 2. Preserve double newlines (paragraphs)
        # 3. Preserve intentional line breaks for lists or code blocks
        
        paragraphs = text.split("\n\n")
        normalized_paragraphs = []
        
        for p in paragraphs:
            lines = p.split("\n")
            # If paragraph looks like a list or has code blocks, preserve newlines
            if any(l.strip().startswith(("-", "*", "1.", "2.", "3.", "`", ">>>")) for l in lines):
                normalized_paragraphs.append(p.strip())
            else:
                # Collapse single newlines into spaces for normal text
                normalized_paragraphs.append(" ".join(l.strip() for l in lines if l.strip()))
        
        return "\n\n".join(normalized_paragraphs)

    def _write_chat(self, who: str, text: str, append: bool = False) -> None:
        if append:
            # We skip per-token writing to avoid fragmentation in RichLog
            return

        prefix = {
            "user": "[bold green]You[/bold green]",
            "agent": "[bold cyan]Agent[/bold cyan]",
            "system": "[yellow]System[/yellow]",
        }.get(who, who)
        self.chat_log.write(f"[dim]{self._timestamp()}[/dim] {prefix}: {text}")

    def _write_event(self, text: str) -> None:
        self.event_log.write(f"[dim]{self._timestamp()}[/dim] {text}")

    def _update_session_panel(self) -> None:
        panel = self.query_one("#session-panel", Static)
        sid = getattr(self.agent, "sid", None) if self.agent else self.session_info.session_id
        panel.update(
            "\n".join(
                [
                    f"Session ID: {sid or 'new'}",
                    f"Provider: {self.session_info.provider.value}",
                    "Interface: tui-v2",
                    f"Last Prompt: {self.last_user_prompt or '-'}",
                ]
            )
        )

    def _update_tools_panel(self, text: str) -> None:
        self.query_one("#tools-panel", Static).update(text)

    def _update_trading_panel(self, text: str) -> None:
        self.query_one("#trading-panel", Static).update(text)

    def _update_logs_panel(self, text: str) -> None:
        self.query_one("#logs-panel", Static).update(text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        if text.startswith("/"):
            await self._handle_command(text)
            return

        self.last_user_prompt = text
        self._update_session_panel()
        self._write_chat("user", text)
        await self._run_agent(text)

    async def _handle_command(self, text: str) -> None:
        command = text.strip().lower()

        if command == "/help":
            self._write_chat("system", "Commands: /help /clear /reset /status")
        elif command == "/clear":
            self.action_clear_chat()
        elif command == "/status":
            sid = getattr(self.agent, "sid", None) or "unknown"
            self._write_chat("system", f"provider={self.session_info.provider.value} session={sid}")
        elif command == "/reset":
            self.agent = Agent(provider=self.session_info.provider, sid=uuid.uuid4().hex[:12])
            self._write_chat("system", "Agent session reset.")
            self._write_event("[yellow]system[/yellow] session reset")
            self._update_session_panel()
        else:
            self._write_chat("system", f"Unknown command: {command}")

    async def _run_agent(self, prompt: str) -> None:
        status = self.query_one("#top-status", TopStatusBar)
        status.state_text = "thinking"
        self._write_event("[blue]agent[/blue] chat request started")
        self._write_event("[dim]awaiting agent response...[/dim]")

        start_time = time.perf_counter()
        queue: Queue = Queue()

        def run_stream():
            try:
                for event in self.agent.chat_stream(prompt):
                    queue.put(event)
            except Exception as e:
                queue.put({"type": "error", "content": str(e)})
            finally:
                queue.put({"type": "done"})

        asyncio.create_task(asyncio.to_thread(run_stream))

        while True:
            while not queue.empty():
                event = queue.get()
                if event["type"] == "done":
                    elapsed = time.perf_counter() - start_time
                    self._write_event(f"[green]agent[/green] chat response completed in {elapsed:.2f}s")
                    status.state_text = "ready"
                    return

                if event["type"] == "token":
                    # We accumulate tokens silently for the main chat log to avoid fragmentation
                    pass
                
                elif event["type"] == "tool_start":
                    self._write_event(f"[dim]calling tool:[/] [cyan]{event['name']}[/]")
                    self._update_tools_panel(f"Last tool: {event['name']}\nInput: {event['input']}")
                
                elif event["type"] == "tool_end":
                    self._write_event(f"[dim]tool finished:[/] [cyan]{event['name']}[/]")
                    res_str = str(event['result'])
                    if len(res_str) > 100:
                        res_str = res_str[:100] + "..."
                    self._update_tools_panel(f"Last tool: {event['name']}\nResult: {res_str}")

                elif event["type"] == "final_response":
                    final_resp = event["content"]
                    normalized = self._normalize_chat_text_for_display(final_resp)
                    self._write_chat("agent", normalized)
                    
                    lower = final_resp.lower()
                    if any(word in lower for word in ("buy", "sell", "hold", "rsi", "volatility", "regime")):
                        self._update_trading_panel(f"Trading detected in response at {self._timestamp()}")

                elif event["type"] == "error":
                    self._write_chat("system", f"Error: {event['content']}")
                    self._write_event(f"[red]error[/red] {event['content']}")
                    self._update_logs_panel(f"Error: {event['content']}")

            await asyncio.sleep(0.05)

    def action_clear_chat(self) -> None:
        self.chat_log.clear()
        self.event_log.clear()
        self._write_chat("system", "Chat cleared.")
        self._write_event("[yellow]system[/yellow] logs cleared")

    def action_focus_input(self) -> None:
        self._focus_input()

    def action_retry_last(self) -> None:
        if not self.last_user_prompt:
            self._write_chat("system", "No last prompt to retry.")
            return
        self._write_event("[blue]agent[/blue] retrying last prompt")
        asyncio.create_task(self._run_agent(self.last_user_prompt))

    def action_show_help(self) -> None:
        self._write_chat("system", "F1 Help | F2 Inspector | F3 Events | Ctrl+K Clear | Ctrl+L Focus | Ctrl+R Retry | Ctrl+C Quit")

    def action_toggle_inspector(self) -> None:
        col = self.query_one("#right-column")
        col.display = not col.display

    def action_toggle_events(self) -> None:
        log = self.query_one("#events-log")
        log.display = not log.display


def run_tui(session_id: Optional[str], provider: ModelProvider) -> None:
    app = ChatTUIv2(session_id=session_id, provider=provider)
    app.run()
