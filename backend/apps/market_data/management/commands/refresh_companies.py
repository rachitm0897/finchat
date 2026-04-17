from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.market_data.clients.finnhub import FinnhubMissingAPIKeyError, FinnhubRateLimitError
from apps.market_data.services import CompanyBatchRefreshService


class Command(BaseCommand):
    help = "Refresh multiple companies from Finnhub."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tickers",
            nargs="+",
            required=True,
            help="List of ticker symbols. Supports space-separated or comma-separated input.",
        )
        parser.add_argument(
            "--skip-statements",
            action="store_true",
            help="Skip reported financial statement ingestion.",
        )
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue processing other tickers if one ticker fails.",
        )

    def handle(self, *args, **options):
        raw_items = options["tickers"] or []
        tickers: list[str] = []
        for item in raw_items:
            tickers.extend([part.strip().upper() for part in str(item).split(",") if part.strip()])

        if not tickers:
            raise CommandError("No valid tickers were provided.")

        try:
            result = CompanyBatchRefreshService().refresh_tickers(
                tickers=tickers,
                ingest_statements=not bool(options["skip_statements"]),
                continue_on_error=bool(options["continue_on_error"]),
            )
        except FinnhubMissingAPIKeyError as exc:
            raise CommandError(str(exc)) from exc
        except FinnhubRateLimitError as exc:
            raise CommandError(f"Finnhub rate limit error: {exc}") from exc
        except Exception as exc:
            raise CommandError(f"Batch refresh failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Refresh finished. requested={result['requested']} "
                f"succeeded={result['succeeded']} failed={result['failed']}"
            )
        )

        for row in result["results"]:
            self.stdout.write(
                f"[OK] {row['ticker']} | company_created={row['company_created']} "
                f"profile_created={row['profile_snapshot_created']} "
                f"quote_created={row['quote_snapshot_created']} "
                f"basic_created={row['basic_metric_snapshot_created']} "
                f"statements={row['statements_result']}"
            )
            for warning in row["warnings"]:
                self.stdout.write(self.style.WARNING(f"  warning: {warning}"))

        for err in result["errors"]:
            self.stdout.write(self.style.ERROR(f"[ERROR] {err['ticker']} | {err['error']}"))