from __future__ import annotations

import uuid

from django.db import models

from apps.market_data.models import Company


class ChatSession(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_ERROR = "error"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
        (STATUS_ERROR, "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    user_identifier = models.CharField(max_length=128, blank=True)
    context_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    companies = models.ManyToManyField(
        Company,
        related_name="chat_sessions",
        blank=True,
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "-updated_at"]),
            models.Index(fields=["user_identifier"]),
            models.Index(fields=["last_message_at"]),
        ]

    def __str__(self) -> str:
        return self.title or f"ChatSession {self.id}"


class ChatMessage(models.Model):
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_TOOL = "tool"

    ROLE_CHOICES = [
        (ROLE_SYSTEM, "System"),
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_TOOL, "Tool"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()

    message_index = models.PositiveIntegerField()
    model_name = models.CharField(max_length=128, blank=True)
    token_usage_input = models.PositiveIntegerField(null=True, blank=True)
    token_usage_output = models.PositiveIntegerField(null=True, blank=True)

    grounding_json = models.JSONField(default=dict, blank=True)
    tool_name = models.CharField(max_length=128, blank=True)
    tool_arguments_json = models.JSONField(default=dict, blank=True)
    source_trace = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["session", "message_index"]
        indexes = [
            models.Index(fields=["session", "message_index"]),
            models.Index(fields=["role"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "message_index"],
                name="uq_chat_message_session_index",
            )
        ]

    def __str__(self) -> str:
        return f"{self.session_id} [{self.role}] #{self.message_index}"