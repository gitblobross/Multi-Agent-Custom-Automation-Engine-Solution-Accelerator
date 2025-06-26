import logging
from datetime import datetime
from typing import Dict, List, Optional

from context.cosmos_memory_kernel import CosmosMemoryContext
from event_utils import track_event_if_configured
from kernel_agents.agent_base import BaseAgent
from models.messages_kernel import (
    ActionRequest,
    AgentMessage,
    AgentType,
    HumanFeedback,
    HumanFeedbackStatus,
    InputTask,
    Plan,
    Step,
    StepStatus,
)
from semantic_kernel.functions.kernel_function import KernelFunction

# ────────────────────────────────────────────────────────────────────────────────
#  GroupChatManager  (orchestrator)
# ────────────────────────────────────────────────────────────────────────────────
class GroupChatManager(BaseAgent):
    """
    Orchestrator for Litigator:
    • Receives InputTask → asks PlannerAgent to break it into steps
    • Routes each step to LawAgent, CasefileAgent, FilingAgent, or HumanAgent
    • Persists all events in Cosmos `conversations` container
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        memory_store: CosmosMemoryContext,
        agent_instances: Dict[str, BaseAgent],
        tools: Optional[List[KernelFunction]] = None,
        system_message: Optional[str] = None,
        agent_name: str = AgentType.GROUP_CHAT_MANAGER.value,
        client=None,
        definition=None,
    ):
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

        # Domain-specific agents available at runtime
        self._agent_instances = agent_instances
        self._available_agents = [
            AgentType.HUMAN.value,
            AgentType.LAW.value,
            AgentType.CASEFILE.value,
            AgentType.FILING.value,
        ]

    # --------------------------------------------------------------------- factory
    @classmethod
    async def create(cls, **kwargs):
        agent_definition = await cls._create_azure_ai_agent_definition(
            agent_name=kwargs["agent_name"],
            instructions=kwargs["system_message"],
            temperature=0.0,
            response_format=None,
        )
        return cls(
            session_id=kwargs["session_id"],
            user_id=kwargs["user_id"],
            memory_store=kwargs["memory_store"],
            agent_instances=kwargs["agent_instances"],
            tools=kwargs.get("tools"),
            system_message=kwargs["system_message"],
            agent_name=kwargs["agent_name"],
            client=kwargs.get("client"),
            definition=agent_definition,
        )

    # ---------------------------------------------------------------- system prompt
    @staticmethod
    def default_system_message() -> str:
        return (
            "You are **GroupChatManager** for Litigator.\n"
            "• Analyse the user's litigation goal.\n"
            "• Ask PlannerAgent to break it into steps.\n"
            "• Assign each step to exactly one of "
            "[LawAgent, CasefileAgent, FilingAgent, HumanAgent].\n"
            "• Track human approvals and mark steps complete.\n"
            "Today's date: {{date}}."
        )

    # ===================================================================== handlers
    async def handle_input_task(self, message: InputTask) -> Plan:
        """Initial user request → store & forward to PlannerAgent."""
        logging.info("GCM received input task: %s", message.description)

        await self._memory_store.add_item(
            AgentMessage(
                session_id=message.session_id,
                user_id=self._user_id,
                plan_id="",
                content=message.description,
                source=AgentType.HUMAN.value,
                step_id="",
            )
        )

        track_event_if_configured(
            "GCM:InputTask",
            {"session_id": message.session_id, "content": message.description},
        )

        planner = self._agent_instances[AgentType.PLANNER.value]
        plan = await planner.handle_input_task(message)  # returns Plan object
        return plan

    async def handle_human_feedback(self, message: HumanFeedback) -> None:
        """Update steps based on approval / rejection."""
        logging.info("GCM received human feedback: %s", message)

        steps: List[Step] = await self._memory_store.get_steps_by_plan(message.plan_id)
        feedback_txt = message.human_feedback or ""
        general_info = f"Today's date is {datetime.now().date()}."
        full_feedback = f"{general_info}\n{feedback_txt}"

        targets = (
            [s for s in steps if s.id == message.step_id]
            if message.step_id
            else steps
        )

        for step in targets:
            await self._update_step_status(step, message.approved, full_feedback)
            if message.approved:
                await self._execute_step(message.session_id, step)

    # ------------------------------------------------------------------ helpers
    async def _update_step_status(self, step: Step, approved: bool, feedback: str):
        step.human_feedback = feedback
        step.human_approval_status = (
            HumanFeedbackStatus.accepted if approved else HumanFeedbackStatus.rejected
        )
        step.status = StepStatus.approved if approved else StepStatus.rejected
        await self._memory_store.update_step(step)

    async def _execute_step(self, session_id: str, step: Step):
        """Send an ActionRequest to the appropriate agent."""
        step.status = StepStatus.action_requested
        await self._memory_store.update_step(step)

        plan = await self._memory_store.get_plan_by_session(session_id)
        hist_steps = await self._memory_store.get_steps_by_plan(plan.id)
        convo = self._format_conversation_history(hist_steps, step.id, plan)

        action_request = ActionRequest(
            step_id=step.id,
            plan_id=step.plan_id,
            session_id=session_id,
            action=f"{convo}\nStep to perform: {step.action}",
            agent=step.agent,
        )

        if step.agent == AgentType.HUMAN:
            step.status = StepStatus.completed
            await self._memory_store.update_step(step)
            return

        agent = self._agent_instances[step.agent.value]
        await agent.handle_action_request(action_request)

    @staticmethod
    def _format_conversation_history(steps: List[Step], current_step: str, plan: Plan):
        out = [
            "<conversation_history>",
            f"User goal: {plan.summary}",
            f"Human clarification: {plan.human_clarification_response or 'None'}",
            "Previous steps:",
        ]
        for i, s in enumerate(steps):
            if s.id == current_step:
                break
            out.append(f"Step {i}: {s.action}")
            out.append(f"{s.agent.value}: {s.agent_reply}")
        out.append("</conversation_history>")
        return "\n".join(out)
