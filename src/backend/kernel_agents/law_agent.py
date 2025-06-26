import logging
from typing import Dict, List, Optional
from context.cosmos_memory_kernel import CosmosMemoryContext
from kernel_agents.agent_base import BaseAgent
from semantic_kernel.functions import KernelFunction
from agents.law_tools import get_law_tools                       # NEW
from models.messages_kernel import AgentType                     # extend enum

SYSTEM_PROMPT = """
You are **Law Agent** for Litigator.

• Answer U.S. federal and California law questions with Bluebook citations.
• Call `law_query` for caselaw/statutes; call `bluebook_cite` to format a cite.
• Begin every reply with “LEGAL ANALYSIS:” and end with “—Law Agent”.
"""

class LawAgent(BaseAgent):
    """Domain agent powered by GPT-o3 + legal tools."""

    def __init__(self,
                 session_id: str,
                 user_id: str,
                 memory_store: CosmosMemoryContext,
                 agent_id,
                 tools: Optional[List[KernelFunction]] = None,
                 system_message: Optional[str] = None,
                 client=None,
                 definition=None):
        tools = tools or get_law_tools()
        system_message = system_message or SYSTEM_PROMPT
        super().__init__(
            agent_name=AgentType.LAW.value,
            session_id=session_id,
            user_id=user_id,
            memory_store=memory_store,
            tools=tools,
            system_message=system_message,
            client=client,
            definition=definition,
        )

    # Factory required by BaseAgent.create
    @classmethod
    async def create(cls, **kwargs: Dict[str, str]):
        return cls(
            session_id=kwargs["session_id"],
            user_id=kwargs["user_id"],
            memory_store=kwargs["memory_store"],
            agent_id=kwargs["agent_id"],
        )
