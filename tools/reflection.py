import threading
import logging
from memory.wisdom import WisdomStore
from core.agent import Agent

logger = logging.getLogger(__name__)

def generate_post_mortem(trade_data: dict) -> None:
    """Run an LLM reflection on a closed trade to extract wisdom."""
    try:
        agent = Agent()
        prompt = f"""
You are an expert crypto trading AI evaluating a recently closed paper trade to learn from it.

Trade Details:
Symbol: {trade_data.get('symbol')}
Action: {trade_data.get('action')}
Entry Price: ${trade_data.get('entry_price')}
Exit Price: ${trade_data.get('exit_price')}
PnL: ${trade_data.get('pnl')}
Strategy/Notes: {trade_data.get('strategy') or trade_data.get('notes')}

Analyze this trade. Did we make money or lose money? What is a short, 1-sentence lesson learned from this specific trade?
Then, write a single "Commandment" - a universal, prescriptive rule for future trading (e.g. "Do not buy assets that have dropped 10% in 1 hour without confirmation").

Respond EXACTLY in this format:
LESSON: <the 1-sentence lesson>
COMMANDMENT: <the prescriptive rule>
"""
        response = agent.chat(prompt)
        lesson = ""
        commandment = ""
        for line in response.split('\n'):
            if line.startswith("LESSON:"):
                lesson = line.replace("LESSON:", "").strip()
            elif line.startswith("COMMANDMENT:"):
                commandment = line.replace("COMMANDMENT:", "").strip()
        
        if lesson or commandment:
            store = WisdomStore()
            if lesson:
                store.add_lesson(trade_data.get('symbol', 'UNKNOWN'), trade_data.get('pnl', 0.0), lesson)
            if commandment:
                store.add_commandment(commandment)
            logger.info(f"Post-mortem reflection completed. Lesson: {lesson}")
    except Exception as e:
        logger.error(f"Failed to generate post-mortem: {e}")

def trigger_post_mortem(trade_data: dict) -> None:
    """Asynchronously triggers the post-mortem analysis."""
    thread = threading.Thread(target=generate_post_mortem, args=(trade_data,), daemon=True)
    thread.start()
