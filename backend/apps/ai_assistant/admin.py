from __future__ import annotations

from django.contrib import admin

from apps.ai_assistant.models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("message_index", "role", "content", "model_name", "tool_name", "created_at")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "user_identifier", "last_message_at", "updated_at")
    search_fields = ("title", "user_identifier")
    list_filter = ("status",)
    filter_horizontal = ("companies",)
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "message_index", "role", "model_name", "tool_name", "created_at")
    search_fields = ("session__title", "content", "tool_name")
    list_filter = ("role", "model_name", "tool_name")