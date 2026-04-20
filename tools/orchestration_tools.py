import logging
import json
from core.tools import register_tool
from core.orchestrator import run_autonomous_cycle, registry

logger = logging.getLogger(__name__)

@register_tool(
    name="trigger_autonomous_cycle",
    description="Manually trigger the full Autonomous Trading Cycle (Alpha collection -> Indicator scanning -> Setup generation -> Risk verification -> Telegram proposal). Use this to force the bot to look for trades immediately.",
    input_schema={
        "type": "object",
        "properties": {
            "chat_id": {"type": "integer", "description": "The Telegram chat ID to send the proposal to."}
        },
        "required": ["chat_id"],
    },
)
def trigger_autonomous_cycle(chat_id: int) -> str:
    """Manually trigger the autonomous cycle."""
    try:
        from threading import Thread
        # Run in a separate thread to avoid blocking the agent
        thread = Thread(target=run_autonomous_cycle, args=(chat_id,))
        thread.start()
        return "Autonomous Trading Cycle triggered in background. Check your Telegram for proposals shortly."
    except Exception as e:
        return f"Error triggering cycle: {e}"

@register_tool(
    name="check_background_processes",
    description="Check the status of currently running or recently completed background tasks (like Autonomous Cycles).",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def check_background_processes() -> str:
    """Check background process registry."""
    processes = registry.get_all()
    if not processes:
        return "No background processes found in the current session."
    
    return "Current Background Processes:\n" + json.dumps(processes, indent=2)
