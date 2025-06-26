# agents/filing_agent.py
import logging
from typing import Dict, List, Optional

from context.cosmos_memory_kernel import CosmosMemoryContext
from kernel_agents.agent_base import BaseAgent
from kernel_tools.filing_tools import FilingTools               # NEW
from models.messages_kernel import AgentType
from semantic_kernel.functions import KernelFunction


class FilingAgent(BaseAgent):
    """
    Drafts pleadings (DOCX/PDF) and optionally e-files them via the /filing/draft
    endpoint. Powered by GPT-o3 (gpt-o3-filing deployment).
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        memory_store: CosmosMemoryContext,
        tools: Optional[List[KernelFunction]] = None,
        system_message: Optional[str] = None,
        agent_name: str = AgentType.FILING.value,
        client=None,
        definition=None,
    ):
        tools = tools or [
            KernelFunction.from_method(fn)
            for fn in FilingTools.get_all_kernel_functions().values()
        ]
        system_message = system_message or self.default_system_message()

        super().__init__(
            agent_name=agent_name,
            session_id=session_id,
            user_id=user_id,
            memory_store=memory_store,
            tools=tools,
            system_message=system_message,
            client=client,
            definition=definition,
        )

    # ---------------- factory used by GroupChatManager.register -------------
    @classmethod
    async def create(cls, **kwargs: Dict[str, str]):
        agent_def = await cls._create_azure_ai_agent_definition(
            agent_name=kwargs["agent_name"],
            instructions=kwargs.get("system_message", cls.default_system_message()),
            temperature=0.0,
            response_format=None,
        )
        return cls(
            session_id=kwargs["session_id"],
            user_id=kwargs["user_id"],
            memory_store=kwargs["memory_store"],
            tools=kwargs.get("tools"),
            system_message=kwargs.get("system_message"),
            agent_name=kwargs["agent_name"],
            client=kwargs.get("client"),
            definition=agent_def,
        )

    # ---------------------------------------------------------------- prompt
    @staticmethod
    def default_system_message() -> str:
        return (
            "You are **FilingAgent**.  Draft pleadings using court-specific "
            "templates and Bluebook citations.  Use `filing_draft` to generate "
            "or e-file documents.  Summarize your work at the end of each reply."
        )

    # ---------------------------------------------------------------- tools property (optional)
    @property
    def plugins(self):
        """Expose FilingTools to the Semantic-Kernel runtime."""
        return FilingTools.get_all_kernel_functions()
