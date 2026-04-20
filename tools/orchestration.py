import logging
from typing import Optional
from core.tools import register_tool
from core.agent import Agent

from core.provider import ModelProvider

logger = logging.getLogger(__name__)

@register_tool(
    name="delegate_task",
    description="Delegate a specific sub-task to a specialized sub-agent (researcher, executor, or risk_manager). Use this to keep your own context clean and leverage experts.",
    input_schema={
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "The role of the sub-agent. Must be one of: researcher, executor, risk_manager.",
                "enum": ["researcher", "executor", "risk_manager"]
            },
            "task": {
                "type": "string",
                "description": "The explicit, detailed task instruction for the sub-agent."
            },
            "provider": {
                "type": "string",
                "description": "Optional: Override the default LLM provider for this task (e.g., 'anthropic', 'openai', 'gemini').",
                "enum": ["anthropic", "openai", "gemini"]
            }
        },
        "required": ["role", "task"],
    },
)
def delegate_task(role: str, task: str, provider: Optional[str] = None) -> str:
    """Instantiate a sub-agent and have it perform a task."""
    valid_roles = ["researcher", "executor", "risk_manager"]
    if role not in valid_roles:
        return f"Error: Invalid role '{role}'. Must be one of {valid_roles}."
    
    selected_provider = None
    if provider:
        try:
            selected_provider = ModelProvider(provider.lower())
        except ValueError:
            return f"Error: Invalid provider '{provider}'."

    logger.info(f"Delegating task to {role} (Provider: {provider or 'default'}): {task}")
    try:
        # Create a new Agent instance with the specific role and provider
        sub_agent = Agent(role=role, provider=selected_provider)
        result = sub_agent.chat(task)
        return f"--- Sub-agent '{role}' completed the task using {sub_agent.provider.value} ---\nResult:\n{result}"
    except Exception as e:
        logger.error(f"Error during delegation to {role}: {e}")
        return f"Error executing delegated task: {e}"

@register_tool(
    name="verify_with_council",
    description="Send a proposed plan or analysis to a different specialized agent for a second opinion. This creates a multi-brain consensus to catch mistakes.",
    input_schema={
        "type": "object",
        "properties": {
            "proposed_plan": {
                "type": "string",
                "description": "The full text of the plan or analysis to be verified."
            },
            "verifier_role": {
                "type": "string",
                "description": "The role of the agent who should verify it. Usually 'risk_manager' for trade plans.",
                "enum": ["researcher", "executor", "risk_manager"],
                "default": "risk_manager"
            },
            "context": {
                "type": "string",
                "description": "Any additional context needed for verification (e.g. recent news, current PnL)."
            }
        },
        "required": ["proposed_plan"],
    },
)
def verify_with_council(proposed_plan: str, verifier_role: str = "risk_manager", context: Optional[str] = None) -> str:
    """Ask another agent role to verify a plan."""
    task = (
        f"I need a second opinion on the following proposed plan:\n\n"
        f"--- PROPOSED PLAN ---\n{proposed_plan}\n\n"
    )
    if context:
        task += f"--- ADDITIONAL CONTEXT ---\n{context}\n\n"
    
    task += (
        "Please critique this plan. Look for risks, logical errors, or violations of trading best practices. "
        "Either approve it with 'APPROVED' and your reasoning, or reject it with 'REJECTED' and specific improvements needed."
    )
    
    return delegate_task(role=verifier_role, task=task)

