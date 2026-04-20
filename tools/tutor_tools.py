import json
import logging
from typing import Optional
from core.tools import register_tool
from backend.paper_trading import get_paper_trading_account
from memory.wisdom import WisdomStore

logger = logging.getLogger(__name__)

@register_tool(
    name="tutor_explain_activity",
    description="Provides a pedagogical breakdown of the bot's recent activity, including why specific trades were taken or rejected and what lessons were learned. Helps users understand the 'Reasoning' behind the AI.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "The user ID of the paper account."},
            "limit": {"type": "integer", "description": "Number of recent events to explain.", "default": 3}
        },
        "required": ["user_id"],
    },
)
def tutor_explain_activity(user_id: int, limit: int = 3) -> str:
    """Explain recent trades and lessons in simple terms."""
    try:
        account = get_paper_trading_account(user_id)
        wisdom = WisdomStore()
        
        trades = list(account.paper_trades)[-limit:] if account else []
        lessons = list(wisdom.get_lessons())[-limit:]
        
        explanation = ["🎓 Trading Tutor: Let's review what happened recently", "================================================"]
        
        if not trades and not lessons:
            return "Class is just starting! No recent trades or lessons to explain yet. Try running an autonomous cycle first."
            
        if trades:
            explanation.append("\n📝 Recent Trades Explained:")
            for t in trades:
                status = "won" if float(t.get("pnl", 0)) > 0 else "lost" if float(t.get("pnl", 0)) < 0 else "closed"
                explanation.append(f"- We {t['action']}ed {t['symbol']} using the {t.get('strategy', 'manual')} strategy.")
                explanation.append(f"  The trade {status} ${abs(float(t.get('pnl', 0))):.2f}.")
                explanation.append(f"  Concept: We entered at ${float(t['entry_price']):.2f} and exited at ${float(t.get('exit_price', 0)):.2f}. This is based on price action alignment.")

        if lessons:
            explanation.append("\n🧠 Wisdom Learned (The 'Why'):")
            for l in lessons:
                explanation.append(f"- On {l['symbol']}, we learned: \"{l['lesson']}\"")
                explanation.append(f"  Teacher's Note: This rule is now part of my 'Commandments'. I will use this to protect us in the future.")

        explanation.append("\n💡 Educational Tip: Always prioritize 'Stillness' over 'Hype'. If a setup doesn't meet our strict criteria in the Wisdom Ledger, the best trade is often no trade at all.")
        
        return "\n".join(explanation)
    except Exception as e:
        logger.error(f"Tutor explanation error: {e}")
        return f"Error in tutor mode: {e}"
