from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.ai_assistant.domain_services import SessionMemoryService
from apps.ai_assistant.graph import run_financial_assistant_graph
from apps.ai_assistant.models import ChatMessage, ChatSession
from apps.market_data.models import Company


@dataclass(slots=True)
class ChatSessionCreateResult:
    session: ChatSession


@dataclass(slots=True)
class ChatSendMessageResult:
    session: ChatSession
    user_message: ChatMessage
    assistant_message: ChatMessage
    reasoning_summary: dict[str, Any]


class FinancialAssistantGraphService:
    def run(
        self,
        user_query: str,
        chat_history: list[dict[str, str]] | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return run_financial_assistant_graph(
            user_query=user_query,
            chat_history=chat_history or [],
            session_context=session_context or {},
        )


class ChatSessionService:
    def create_session(
        self,
        *,
        title: str = "",
        context_json: dict[str, Any] | None = None,
        user_identifier: str = "",
    ) -> ChatSessionCreateResult:
        session = ChatSession.objects.create(
            title=title.strip(),
            context_json=self._to_json_safe(context_json or {}),
            user_identifier=user_identifier.strip(),
            status=ChatSession.STATUS_ACTIVE,
        )
        return ChatSessionCreateResult(session=session)

    def list_sessions(self, limit: int = 20):
        return list(ChatSession.objects.prefetch_related("companies").order_by("-updated_at")[:limit])

    def get_session(self, session_id: str | UUID) -> ChatSession | None:
        return (
            ChatSession.objects.prefetch_related("companies")
            .filter(id=session_id)
            .first()
        )

    def list_messages(self, session_id: str | UUID):
        return list(
            ChatMessage.objects.filter(session_id=session_id)
            .order_by("message_index")
        )

    @transaction.atomic
    def send_message(
        self,
        *,
        session_id: str | UUID,
        content: str,
    ) -> ChatSendMessageResult:
        session = ChatSession.objects.select_for_update().filter(id=session_id).first()
        if session is None:
            raise ValueError("Chat session not found.")

        content = content.strip()
        if not content:
            raise ValueError("Message content must not be empty.")

        next_index = (
            ChatMessage.objects.filter(session=session).aggregate(max_idx=Max("message_index"))["max_idx"] or 0
        ) + 1

        user_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content=content,
            message_index=next_index,
        )

        if not session.title:
            session.title = content[:80]
            session.save(update_fields=["title", "updated_at"])

        chat_history = self._build_graph_history(session)
        memory_context = self._build_session_memory_context(session)
        if memory_context:
            chat_history.insert(
                0,
                {
                    "role": "assistant",
                    "content": memory_context,
                },
            )

        graph_result = FinancialAssistantGraphService().run(
            user_query=content,
            chat_history=chat_history,
            session_context=session.context_json or {},
        )

        final_answer = graph_result.get("final_answer", "") or ""
        planner_output = graph_result.get("planner_output", {}) or {}
        resolved_companies = graph_result.get("resolved_companies", []) or []
        tool_results = graph_result.get("tool_results", {}) or {}
        errors = graph_result.get("errors", []) or []

        metric_codes_used = sorted(self._extract_metric_codes(tool_results))
        companies_used = resolved_companies

        safe_grounding_json = self._to_json_safe(
            {
                "planner_output": planner_output,
                "resolved_companies": resolved_companies,
                "tool_results": tool_results,
                "errors": errors,
            }
        )

        safe_source_trace = self._to_json_safe(
            {
                "companies_used": companies_used,
                "metric_codes_used": metric_codes_used,
            }
        )

        assistant_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content=final_answer,
            message_index=next_index + 1,
            model_name=getattr(settings, "LLM_MODEL_NAME", ""),
            grounding_json=safe_grounding_json,
            source_trace=safe_source_trace,
        )

        context_json = SessionMemoryService().build_memory_update(
            existing_context=self._to_json_safe(session.context_json or {}),
            resolved_companies=companies_used,
            metric_codes_used=metric_codes_used,
            intent=planner_output.get("intent"),
            analysis_modes=planner_output.get("analysis_modes", []),
            query=content,
        )
        context_json = self._to_json_safe(context_json)

        session.context_json = context_json
        session.last_message_at = timezone.now()
        session.status = ChatSession.STATUS_ACTIVE if not errors else ChatSession.STATUS_ERROR
        session.save(update_fields=["context_json", "last_message_at", "status", "updated_at"])

        return ChatSendMessageResult(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            reasoning_summary=self._to_json_safe(
                {
                    "intent": planner_output.get("intent"),
                    "analysis_modes": planner_output.get("analysis_modes", []),
                    "companies_used": companies_used,
                    "metric_codes_used": metric_codes_used,
                    "errors": errors,
                }
            ),
        )

    def _build_graph_history(self, session: ChatSession) -> list[dict[str, str]]:
        history = []
        for msg in ChatMessage.objects.filter(session=session).order_by("message_index"):
            if msg.role in {ChatMessage.ROLE_USER, ChatMessage.ROLE_ASSISTANT}:
                history.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )
        return history[-12:]

    def _build_session_memory_context(self, session: ChatSession) -> str:
        context = session.context_json or {}
        memory = context.get("memory") or {}
        if not memory:
            return ""

        companies = memory.get("last_companies_used") or []
        metric_codes = memory.get("last_metric_codes_used") or []
        last_intent = memory.get("last_intent")
        analysis_modes = memory.get("last_analysis_modes") or []

        return (
            "Session memory:\n"
            f"- Last companies used: {', '.join(companies) if companies else 'none'}\n"
            f"- Last metric codes used: {', '.join(metric_codes[:10]) if metric_codes else 'none'}\n"
            f"- Last intent: {last_intent or 'unknown'}\n"
            f"- Last analysis modes: {', '.join(analysis_modes) if analysis_modes else 'none'}"
        )

    def _extract_metric_codes(self, payload: Any) -> set[str]:
        codes: set[str] = set()

        def walk(obj: Any):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "metric_code" and isinstance(value, str):
                        codes.add(value)
                    else:
                        walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(payload)
        return codes

    def _to_json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]

        return str(value)