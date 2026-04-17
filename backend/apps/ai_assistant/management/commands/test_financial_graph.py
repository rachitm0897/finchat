from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.services import FinancialAssistantGraphService


class Command(BaseCommand):
    help = "Run a local LangGraph financial assistant workflow test."

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            required=True,
            help="User query to run through the LangGraph workflow.",
        )
        parser.add_argument(
            "--show-state",
            action="store_true",
            help="Print the full final graph payload as JSON.",
        )

    def handle(self, *args, **options):
        query = str(options["query"]).strip()
        show_state = bool(options["show_state"])

        if not query:
            raise CommandError("Query must not be empty.")

        try:
            result = FinancialAssistantGraphService().run(user_query=query)
        except Exception as exc:
            raise CommandError(f"LangGraph workflow failed: {exc}") from exc

        final_answer = result.get("final_answer", "")
        final_payload = result.get("final_payload", {})

        self.stdout.write(self.style.SUCCESS("Graph workflow completed.\n"))
        self.stdout.write("FINAL ANSWER:\n")
        self.stdout.write(str(final_answer))

        if show_state:
            self.stdout.write("\n\nFINAL STATE PAYLOAD:\n")
            self.stdout.write(json.dumps(final_payload, indent=2, default=str))