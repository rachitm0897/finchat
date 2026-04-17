from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.market_data.clients.finnhub import (
    FinnhubMissingAPIKeyError,
    FinnhubNotFoundError,
    FinnhubRateLimitError,
)
from apps.market_data.services import CompanyIngestionService


class Command(BaseCommand):
    help = "Ingest one company from Finnhub by ticker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            required=True,
            help="Ticker symbol to ingest, for example AAPL.",
        )
        parser.add_argument(
            "--skip-statements",
            action="store_true",
            help="Skip reported financial statement ingestion.",
        )

    def handle(self, *args, **options):
        ticker = str(options["ticker"]).strip().upper()
        skip_statements = bool(options["skip_statements"])

        try:
            result = CompanyIngestionService().ingest_company(
                ticker=ticker,
                ingest_statements=not skip_statements,
            )
        except FinnhubMissingAPIKeyError as exc:
            raise CommandError(str(exc)) from exc
        except FinnhubNotFoundError as exc:
            raise CommandError(f"Ticker '{ticker}' could not be resolved: {exc}") from exc
        except FinnhubRateLimitError as exc:
            raise CommandError(f"Finnhub rate limit error: {exc}") from exc
        except Exception as exc:
            raise CommandError(f"Ingestion failed for ticker '{ticker}': {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Ingestion completed for {result.ticker}"))
        self.stdout.write(f"Company ID: {result.company_id}")
        self.stdout.write(f"Company created: {result.company_created}")
        self.stdout.write(f"Profile snapshot created: {result.profile_snapshot_created}")
        self.stdout.write(f"Quote snapshot created: {result.quote_snapshot_created}")
        self.stdout.write(f"Basic metric snapshot created: {result.basic_metric_snapshot_created}")
        self.stdout.write(f"Statements result: {result.statements_result}")

        if result.warnings:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warning in result.warnings:
                self.stdout.write(f" - {warning}")