import logging
import time
import json
import threading
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from core.agent import Agent
from core.notifications import send_telegram_message
from memory.proposals import ProposalStore
from backend.market_data import TRADING_SYMBOLS

logger = logging.getLogger(__name__)

class PIDLock:
    """Ensure only one instance of a process is running."""
    def __init__(self, name: str):
        self.lock_file = Path.home() / ".agent" / f"{name}.pid"
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self) -> bool:
        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text().strip())
                # Check if process is actually running
                os.kill(pid, 0)
                logger.error(f"Process already running with PID {pid}")
                return False
            except (ProcessLookupError, ValueError, OSError):
                # Process is dead, stale lock
                self.lock_file.unlink()

        self.lock_file.write_text(str(os.getpid()))
        return True

    def release(self):
        if self.lock_file.exists():
            self.lock_file.unlink()

# Global registry for background processes
class ProcessRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProcessRegistry, cls).__new__(cls)
                cls._instance.processes = {}
        return cls._instance

    def register(self, name: str, data: Dict[str, Any]):
        with self._lock:
            self.processes[name] = {
                **data,
                "start_time": datetime.now().isoformat(),
                "status": "running",
            }

    def update(self, name: str, status: str, result: Optional[str] = None):
        with self._lock:
            if name in self.processes:
                self.processes[name]["status"] = status
                self.processes[name]["last_update"] = datetime.now().isoformat()
                if result:
                    self.processes[name]["result"] = result

    def get_active(self) -> List[Dict[str, Any]]:
        with self._lock:
            now = datetime.now()
            to_delete: list[str] = []
            for name, process in self.processes.items():
                if process["status"] != "running":
                    update_time = datetime.fromisoformat(process.get("last_update", process["start_time"]))
                    if now - update_time > timedelta(hours=1):
                        to_delete.append(name)

            for name in to_delete:
                del self.processes[name]

            return [process for process in self.processes.values() if process["status"] == "running"]

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return self.processes.copy()

registry = ProcessRegistry()

def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON object from a string that might contain other text."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
        return {}
    except:
        return {}

def run_autonomous_cycle(target_chat_id: int):
    """
    Main autonomous trading cycle.
    1. Aggregates alpha news.
    2. Scans for pro technical signals.
    3. Generates swing setups.
    4. Council Vote: Risk Manager + Alpha Validator.
    5. Proposes to user ONLY if consensus is reached.
    """
    process_id = f"cycle_{int(time.time())}"
    registry.register(process_id, {"type": "Autonomous Cycle", "chat_id": target_chat_id})
    
    logger.info("Starting Autonomous Trading Cycle (Council Mode)...")
    
    try:
        researcher = Agent(role="researcher", sid="auto_cycle_research")
        risk_manager = Agent(role="risk_manager", sid="auto_cycle_risk")
        validator = Agent(role="validator", sid="auto_cycle_validator")
        
        # 1. Get Alpha
        alpha_report = researcher.chat("Generate a concise daily alpha report for the top 3 crypto assets. Do not use tools if you already have the news.")
        logger.info("Alpha report generated.")

        # 2. Scan Symbols
        symbols = ["BTC", "ETH", "SOL"] 
        proposals_count = 0
        
        for symbol in symbols:
            try:
                logger.info(f"Analyzing {symbol}...")
                indicators_raw = researcher.chat(f"Get pro indicators for {symbol}. Return ONLY the JSON output.")
                indicators = _extract_json(indicators_raw)
                
                if indicators.get("trend") == "UP" or "STRONG" in indicators.get("trend_strength", ""):
                    # 3. Get Swing Setup
                    setup_raw = researcher.chat(f"Generate a swing trade setup for {symbol}. Return ONLY the JSON output.")
                    setup = _extract_json(setup_raw)
                    
                    if "HIGH" in setup.get("setup_quality", "") or "PREMIUM" in setup.get("setup_quality", ""):
                        # 4. Phase A: Risk Manager Verification
                        risk_prompt = (
                            f"I found a high-quality swing setup for {symbol}.\n"
                            f"Setup: {setup_raw}\n"
                            f"Recent Alpha: {alpha_report}\n"
                            "Verify this against our risk rules. Respond with JSON: {\"propose\": bool, \"reason\": \"str\"}"
                        )
                        risk_res = _extract_json(risk_manager.chat(risk_prompt))

                        if risk_res.get("propose"):
                            # 4. Phase B: Alpha Validator (Devil's Advocate)
                            val_prompt = (
                                f"The Researcher and Risk Manager have APPROVED a trade for {symbol}.\n"
                                f"Setup: {setup_raw}\n"
                                "Your job is to be the DEVIL'S ADVOCATE. Why is this trade a BAD idea? "
                                "Check volume, orderbook, and recent news. Respond with JSON: {\"approve\": bool, \"critique\": \"str\"}"
                            )
                            val_res = _extract_json(validator.chat(val_prompt))

                            if val_res.get("approve"):
                                # 5. Consensus Reached - Store and Notify
                                store = ProposalStore()
                                proposal_id = store.add_proposal({
                                    "symbol": symbol,
                                    "setup": setup,
                                    "reason": f"Council Consensus: {risk_res.get('reason')} | Validator: {val_res.get('critique')}",
                                    "type": "SWING"
                                })
                                
                                msg = (
                                    f"🏛️ **COUNCIL APPROVED PROPOSAL**\n\n"
                                    f"Asset: #{symbol} | Quality: {setup.get('setup_quality')}\n\n"
                                    f"**Risk Mgr**: ✅ {risk_res.get('reason')}\n"
                                    f"**Validator**: ✅ {val_res.get('critique')}\n\n"
                                    f"**Plan:**\n"
                                    f"- Entry: {setup.get('trade_plan', {}).get('entry_range')}\n"
                                    f"- Stop: {setup.get('trade_plan', {}).get('stop_loss')}\n"
                                    f"- Target: {setup.get('trade_plan', {}).get('take_profit')}\n"
                                    f"- RR Ratio: {setup.get('trade_plan', {}).get('risk_reward_ratio')}\n\n"
                                    f"Council vote is UNANIMOUS. Reply below to execute."
                                )
                                
                                buttons = {"inline_keyboard": [[
                                    {"text": "✅ EXECUTE", "callback_data": f"proposal:execute:{proposal_id}"},
                                    {"text": "❌ REJECT", "callback_data": f"proposal:reject:{proposal_id}"}
                                ]]}
                                
                                send_telegram_message(target_chat_id, msg, reply_markup=buttons)
                                proposals_count += 1
                                logger.info(f"Consensus proposal sent for {symbol}.")
                            else:
                                logger.warning(f"Validator REJECTED {symbol}: {val_res.get('critique')}")
            except Exception as e:
                logger.error(f"Error in cycle for {symbol}: {e}")

        registry.update(process_id, "completed", f"Found {proposals_count} council-approved opportunities.")
        if proposals_count == 0:
            send_telegram_message(target_chat_id, "🔍 **Council Cycle Complete**\n\nNo trade setups reached a 100% consensus today. The Validator rejected weaker setups to protect your capital. Next scan in 4 hours.")

    except Exception as e:
        logger.error(f"Failed autonomous cycle: {e}")
        registry.update(process_id, "failed", str(e))

def autonomous_orchestrator_loop():
    """Background loop for the autonomous orchestrator."""
    logger.info("Starting Autonomous Orchestrator background loop...")
    
    # Simple wait for system to stabilize
    time.sleep(30)
    
    while True:
        try:
            # Attempt to find a chat_id from the session files
            session_dir = Path.home() / ".agent" / "telegram_sessions"
            chat_id = None
            if session_dir.exists():
                files = list(session_dir.glob("user_*.json"))
                if files:
                    # Extract ID from user_12345.json
                    filename = files[0].name
                    chat_id = int(filename.split("_")[1].split(".")[0])
            
            if chat_id:
                run_autonomous_cycle(chat_id)
            else:
                logger.warning("No Telegram user found to send proposals to. Waiting...")
                
            # Run every 4 hours
            time.sleep(14400)
        except Exception as e:
            logger.error(f"Error in autonomous orchestrator loop: {e}")
            time.sleep(300)
