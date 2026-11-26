from app.guardrails.service import (
    GuardrailService,
)
from ..memory.repository import MemoryRepository

from app.services.agent_service import (
    AgentResult,
    AgentService,
)


class ConversationNotFound(Exception):
    pass


class MemoryLimitReached(Exception):
    pass


class ConversationService:

    def __init__(
        self,
        repository: MemoryRepository,
        agent: AgentService,
        guardrails: GuardrailService,
        max_context_messages: int = 8,
    ):
        self.repository = repository
        self.agent = agent
        self.guardrails = guardrails
        self.max_context_messages = max_context_messages

    def ensure_exists(
        self,
        conversation_id: str,
    ) -> None:
        if not self.repository.conversation_exists(
            conversation_id
        ):
            raise ConversationNotFound(
                "Conversación no encontrada"
            )

    def create(self) -> str:
        return self.repository.create_conversation()

    def list_conversations(self) -> list[dict]:
        return self.repository.list_conversations()

    def messages(
        self,
        conversation_id: str,
    ) -> list[dict[str, str]]:

        self.ensure_exists(conversation_id)

        return self.repository.list_messages(
            conversation_id
        )

    def memories(
        self,
        conversation_id: str,
    ) -> list[dict[str, str]]:

        self.ensure_exists(conversation_id)

        return self.repository.list_memories(
            conversation_id
        )

    def remember(
        self,
        conversation_id: str,
        fact: str,
    ) -> dict[str, str]:

        self.ensure_exists(conversation_id)

        checked = self.guardrails.check_input(
            fact
        )

        if len(
            self.repository.list_memories(
                conversation_id
            )
        ) >= 10:
            raise MemoryLimitReached(
                "Máximo de 10 memorias por conversación"
            )

        return self.repository.add_memory(
            conversation_id,
            checked,
        )

    def forget(
        self,
        conversation_id: str,
        memory_id: str,
    ) -> bool:

        self.ensure_exists(conversation_id)

        return self.repository.delete_memory(
            conversation_id,
            memory_id,
        )

    def delete(
        self,
        conversation_id: str,
    ) -> None:

        self.ensure_exists(conversation_id)

        self.repository.delete_conversation(
            conversation_id
        )

    async def reply(
        self,
        conversation_id: str,
        question: str,
        *,
        temperature: float = 0.3,
        top_p: float = 1.0,
        max_tokens: int = 300,
        confirm_actions: bool = False,
        max_steps: int = 3,
    ) -> tuple[AgentResult, int]:

        # 1. Verificar que la conversación existe.
        self.ensure_exists(conversation_id)

        # 2. Validar la pregunta antes del LLM.
        safe_question = (
            self.guardrails.check_input(question)
        )

        # 3. Recuperar el contexto conversacional.
        history = self.repository.list_messages(
            conversation_id,
            limit=self.max_context_messages,
        )

        # 4. Recuperar las memorias explícitas.
        facts = [
            entry["fact"]
            for entry in self.repository.list_memories(
                conversation_id
            )
        ]

        # 5. Ejecutar el agente del Módulo III.
        result = await self.agent.ask(
            safe_question,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            confirm_actions=confirm_actions,
            max_steps=max_steps,
            history=history,
            memory_facts=facts,
        )

        # 6. Validar la respuesta del modelo.
        safe_answer = (
            self.guardrails.check_output(
                result.answer
            )
        )

        # 7. Persistir la conversación.
        self.repository.save_turn(
            conversation_id,
            safe_question,
            safe_answer,
        )

        # 8. Devolver respuesta y cantidad
        # de mensajes anteriores enviados.
        return (
            AgentResult(
                answer=safe_answer,
                tools_used=result.tools_used,
            ),
            len(history),
        )