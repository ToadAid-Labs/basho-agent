import json
import logging
from typing import Dict, List, Any, Optional
from core.tools import register_tool
from backend.paper_trading import get_paper_trading_account
from memory.wisdom import WisdomStore
from core.agent import Agent

logger = logging.getLogger(__name__)

@register_tool(
    name="audit_strategy_performance",
    description="Analyze paper trading history to attribute PnL and win-rate to specific strategies. Identifies which trading styles are making money and which are losing.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "The user ID of the paper account."}
        },
        "required": ["user_id"],
    },
)
def audit_strategy_performance(user_id: int) -> str:
    """Analyze performance per strategy."""
    try:
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}."
            
        trades = account.paper_trades
        if not trades:
            return "No trade history available to audit."
            
        # Group by strategy
        stats = {}
        for t in trades:
            strat = t.get("strategy") or "UNKNOWN"
            if strat not in stats:
                stats[strat] = {"pnl": 0.0, "wins": 0, "losses": 0, "total": 0}
            
            pnl = float(t.get("pnl", 0.0))
            stats[strat]["pnl"] += pnl
            stats[strat]["total"] += 1
            if pnl > 0:
                stats[strat]["wins"] += 1
            elif pnl < 0:
                stats[strat]["losses"] += 1
                
        report = ["📊 STRATEGY PERFORMANCE AUDIT", "============================"]
        for strat, s in stats.items():
            win_rate = (s["wins"] / s["total"]) * 100 if s["total"] > 0 else 0
            report.append(f"\n🔹 Strategy: {strat}")
            report.append(f"  - Total PnL: ${s['pnl']:.2f}")
            report.append(f"  - Win Rate: {win_rate:.1f}% ({s['total']} trades)")
            report.append(f"  - Avg PnL: ${s['pnl']/s['total']:.2f}")
            
        # Overall summary
        total_pnl = sum(s["pnl"] for s in stats.values())
        report.append("\n----------------------------")
        report.append(f"TOTAL PORTFOLIO PnL: ${total_pnl:.2f}")
        
        return "\n".join(report)
    except Exception as e:
        logger.error(f"Audit error: {e}")
        return f"Error auditing performance: {e}"

@register_tool(
    name="prune_wisdom_ledger",
    description="Self-pruning mechanism for the Wisdom Ledger. Analyzes current 'Commandments' against trade outcomes and suggests removing rules that are statistically linked to losses or have become redundant.",
    input_schema={
        "type": "object",
        "properties": {
            "perform_removal": {
                "type": "boolean", 
                "description": "If true, actually remove the suggested commandments. If false, just list them.",
                "default": False
            }
        }
    },
)
def prune_wisdom_ledger(perform_removal: bool = False) -> str:
    """Analyze and prune the wisdom ledger."""
    try:
        store = WisdomStore()
        commandments = store.get_commandments()
        lessons = store.get_lessons()
        
        if not commandments:
            return "Wisdom Ledger is already empty."
            
        # Use the Risk Manager to analyze the correlation
        # We'll provide the LLM with the full ledger and ask it to find conflicts or failing rules
        agent = Agent(role="risk_manager", sid="wisdom_pruning")
        
        prompt = (
            "I need you to audit our Trading Wisdom Ledger. Your goal is to 'Prune' the ledger—identify rules that are counter-productive, "
            "redundant, or mathematically proven to be incorrect based on our recent lessons.\n\n"
            f"CURRENT COMMANDMENTS:\n{json.dumps(commandments, indent=2)}\n\n"
            f"RECENT TRADE LESSONS:\n{json.dumps(lessons[-20:], indent=2)}\n\n"
            "Analyze these. Are any commandments causing us to lose money? Are any rules redundant?\n"
            "Return a JSON object with: \n"
            "1. 'analysis': a brief string explaining your logic.\n"
            "2. 'to_remove': a list of EXACT commandment strings to delete.\n"
            "Return ONLY the JSON."
        )
        
        response_raw = agent.chat(prompt)
        
        # Extract JSON
        import re
        match = re.search(r'\{.*\}', response_raw, re.DOTALL)
        if not match:
            return f"Agent failed to provide a structured pruning analysis. Response: {response_raw}"
            
        analysis = json.loads(match.group())
        to_remove = analysis.get("to_remove", [])
        
        output = [f"🧠 Wisdom Pruning Analysis: {analysis.get('analysis')}"]
        
        if not to_remove:
            output.append("\n✅ No commandments currently need pruning.")
            return "\n".join(output)
            
        output.append("\nSuggested removals:")
        for cmd in to_remove:
            output.append(f"- {cmd}")
            
        if perform_removal:
            # Re-save commandments without the pruned ones
            new_commandments = [c for c in commandments if c not in to_remove]
            # Since WisdomStore doesn't have a bulk set, we manually update the file for now
            data = store._load()
            data["commandments"] = new_commandments
            store._save(data)
            output.append("\n✨ Pruning complete. Ledger updated.")
        else:
            output.append("\n(Dry run: No changes were made to the ledger. Set perform_removal=True to prune.)")
            
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"Pruning error: {e}")
        return f"Error pruning wisdom ledger: {e}"
