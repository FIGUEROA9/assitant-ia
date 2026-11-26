import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.config import get_settings

from app.guardrails.service import (
    GuardrailService,
    GuardrailViolation,
    OutputGuardrailViolation,
)

from ..memory.repository import MemoryRepository

from app.providers.openrouter import (
    LLMProviderError,
    OpenRouterProvider,
)

from app.schemas.conversation import (
    ConversationCreated,
    ConversationReplyRequest,
    ConversationReplyResponse,
    ConversationSummary,
    MemoryCreate,
    MemoryItem,
    MessagesResponse,
)

from app.services.agent_service import (
    AgentExecutionError,
    AgentService,
)

from app.services.conversation_service import (
    ConversationNotFound,
    ConversationService,
    MemoryLimitReached,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["Conversations (Módulo IV)"],
)


# --------------------------------------------------
# Dependencia: construye el servicio de conversaciones
# --------------------------------------------------

def get_conversation_service() -> ConversationService:

    settings = get_settings()

    provider = OpenRouterProvider(
        settings.openrouter_api_key,
        settings.openrouter_model,
        settings.openrouter_base_url,
    )

    return ConversationService(
        MemoryRepository(
            settings.memory_db_path
        ),
        AgentService(provider),
        GuardrailService(),
        max_context_messages=(
            settings.max_context_messages
        ),
    )


def require_found(
    exc: ConversationNotFound,
) -> HTTPException:

    return HTTPException(
        status_code=404,
        detail=str(exc),
    )


# --------------------------------------------------
# Crear conversación
# --------------------------------------------------

@router.post(
    "",
    response_model=ConversationCreated,
    status_code=201,
)
def create_conversation(
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    return {
        "conversation_id": service.create()
    }


# --------------------------------------------------
# Listar conversaciones
# --------------------------------------------------

@router.get(
    "",
    response_model=list[ConversationSummary],
)
def list_conversations(
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    return service.list_conversations()


# --------------------------------------------------
# Consultar historial
# --------------------------------------------------

@router.get(
    "/{conversation_id}/messages",
    response_model=MessagesResponse,
)
def get_messages(
    conversation_id: UUID,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:
        messages = service.messages(
            str(conversation_id)
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc

    return {
        "conversation_id": conversation_id,
        "messages": messages,
    }


# --------------------------------------------------
# Enviar mensaje al agente con memoria
# --------------------------------------------------

@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationReplyResponse,
)
async def send_message(
    conversation_id: UUID,
    request: ConversationReplyRequest,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:

        result, context_count = await service.reply(
            str(conversation_id),
            request.question,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            confirm_actions=request.confirm_actions,
            max_steps=request.max_steps,
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc

    except OutputGuardrailViolation as exc:
        raise HTTPException(
            status_code=502,
            detail="Respuesta bloqueada por guardrails",
        ) from exc

    except GuardrailViolation as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except (
        AgentExecutionError,
        LLMProviderError,
    ) as exc:

        logger.warning(
            "Error del agente: %s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail="No se pudo completar la inferencia",
        ) from exc

    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "model": get_settings().openrouter_model,
        "tools_used": result.tools_used,
        "context_messages": context_count,
    }


# --------------------------------------------------
# Consultar memorias explícitas
# --------------------------------------------------

@router.get(
    "/{conversation_id}/memories",
    response_model=list[MemoryItem],
)
def list_memories(
    conversation_id: UUID,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:
        return service.memories(
            str(conversation_id)
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc


# --------------------------------------------------
# Guardar una memoria explícita
# --------------------------------------------------

@router.post(
    "/{conversation_id}/memories",
    response_model=MemoryItem,
    status_code=201,
)
def add_memory(
    conversation_id: UUID,
    request: MemoryCreate,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:
        return service.remember(
            str(conversation_id),
            request.fact,
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc

    except GuardrailViolation as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except MemoryLimitReached as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# Eliminar una memoria explícita
# --------------------------------------------------

@router.delete(
    "/{conversation_id}/memories/{memory_id}",
    status_code=204,
)
def delete_memory(
    conversation_id: UUID,
    memory_id: UUID,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:
        deleted = service.forget(
            str(conversation_id),
            str(memory_id),
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Memoria no encontrada",
        )


# --------------------------------------------------
# Eliminar una conversación completa
# --------------------------------------------------

@router.delete(
    "/{conversation_id}",
    status_code=204,
)
def delete_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(
        get_conversation_service
    ),
):

    try:
        service.delete(
            str(conversation_id)
        )

    except ConversationNotFound as exc:
        raise require_found(exc) from exc