from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company


class Command(BaseCommand):
    help = "Compute deterministic financial metrics for one ticker or all companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            required=False,
            help="Ticker symbol to compute metrics for, for example AAPL.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Compute metrics for all companies.",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="When used with --all, only process active companies.",
        )
        parser.add_argument(
            "--calc-version",
            default="v1",
            help="Calculation version label to store in ComputedMetricSnapshot.calculation_version.",
        )

    def handle(self, *args, **options):
        ticker = options.get("ticker")
        run_all = bool(options.get("all"))
        active_only = bool(options.get("active_only"))
        version = str(options.get("calc_version") or "v1").strip()

        if not ticker and not run_all:
            raise CommandError("Provide either --ticker <TICKER> or --all.")

        if ticker and run_all:
            raise CommandError("Use either --ticker or --all, not both.")

        service = MetricComputationService(calculation_version=version)

        if ticker:
            normalized_ticker = ticker.strip().upper()
            if not Company.objects.filter(ticker=normalized_ticker).exists():
                raise CommandError(f"Ticker '{normalized_ticker}' does not exist in Company.")
            result = service.compute_metrics_for_ticker(normalized_ticker)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Metrics computed for {result.ticker} | "
                    f"periods_seen={result.periods_seen} "
                    f"written={result.metrics_written} "
                    f"updated={result.metrics_updated} "
                    f"skipped={result.metrics_skipped}"
                )
            )
            return

        summary = service.compute_metrics_for_all_companies(active_only=active_only)
        self.stdout.write(
            self.style.SUCCESS(
                f"Metrics computed for {summary['companies_processed']} companies."
            )
        )
        for result in summary["results"]:
            self.stdout.write(
                f"[OK] {result.ticker} | periods_seen={result.periods_seen} "
                f"written={result.metrics_written} "
                f"updated={result.metrics_updated} "
                f"skipped={result.metrics_skipped}"
            )