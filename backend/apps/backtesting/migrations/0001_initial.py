from __future__ import annotations

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("jobs", "0001_initial"),
        ("market_data", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StrategyConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("strategy_type", models.CharField(choices=[("sma_crossover", "SMA Crossover")], max_length=64)),
                ("description", models.TextField(blank=True)),
                ("config_json", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="BacktestRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("strategy_type", models.CharField(max_length=64)),
                ("resolution", models.CharField(default="D", max_length=16)),
                ("benchmark_symbol", models.CharField(blank=True, max_length=32)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("initial_capital", models.DecimalField(decimal_places=4, default=10000, max_digits=24)),
                ("position_size", models.DecimalField(decimal_places=6, default=1, max_digits=12)),
                ("commission_bps", models.DecimalField(decimal_places=6, default=10, max_digits=12)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("success", "Success"), ("failed", "Failed")], default="pending", max_length=32)),
                ("request_payload_json", models.JSONField(blank=True, default=dict)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("error_payload_json", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="backtest_runs", to="market_data.company")),
                ("job_run", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="backtest_run", to="jobs.jobrun")),
                ("strategy_config", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="backtest_runs", to="backtesting.strategyconfig")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="BacktestResult",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("metrics_json", models.JSONField(blank=True, default=dict)),
                ("equity_curve_json", models.JSONField(blank=True, default=list)),
                ("drawdown_curve_json", models.JSONField(blank=True, default=list)),
                ("signal_curve_json", models.JSONField(blank=True, default=list)),
                ("trades_json", models.JSONField(blank=True, default=list)),
                ("monthly_return_table_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("backtest_run", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="result", to="backtesting.backtestrun")),
            ],
        ),
        migrations.CreateModel(
            name="BacktestPriceBar",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_name", models.CharField(default="finnhub", max_length=64)),
                ("symbol", models.CharField(db_index=True, max_length=32)),
                ("resolution", models.CharField(choices=[("D", "Daily")], default="D", max_length=16)),
                ("start_at", models.DateTimeField(db_index=True)),
                ("end_at", models.DateTimeField(db_index=True)),
                ("open_price", models.DecimalField(decimal_places=6, max_digits=24)),
                ("high_price", models.DecimalField(decimal_places=6, max_digits=24)),
                ("low_price", models.DecimalField(decimal_places=6, max_digits=24)),
                ("close_price", models.DecimalField(decimal_places=6, max_digits=24)),
                ("volume", models.DecimalField(decimal_places=6, default=0, max_digits=24)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("fetched_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="backtest_price_bars", to="market_data.company")),
            ],
            options={"ordering": ["start_at"]},
        ),
        migrations.AddIndex(
            model_name="strategyconfig",
            index=models.Index(fields=["strategy_type", "is_active"], name="backtest_st_strateg_4ce0f0_idx"),
        ),
        migrations.AddIndex(
            model_name="backtestrun",
            index=models.Index(fields=["company", "-created_at"], name="backtest_ba_company_9c1654_idx"),
        ),
        migrations.AddIndex(
            model_name="backtestrun",
            index=models.Index(fields=["status", "-created_at"], name="backtest_ba_status_14740a_idx"),
        ),
        migrations.AddIndex(
            model_name="backtestrun",
            index=models.Index(fields=["strategy_type", "-created_at"], name="backtest_ba_strateg_7d7594_idx"),
        ),
        migrations.AddIndex(
            model_name="backtestpricebar",
            index=models.Index(fields=["company", "resolution", "start_at"], name="backtest_pr_company_583977_idx"),
        ),
        migrations.AddIndex(
            model_name="backtestpricebar",
            index=models.Index(fields=["symbol", "resolution", "start_at"], name="backtest_pr_symbol_355177_idx"),
        ),
        migrations.AddConstraint(
            model_name="backtestpricebar",
            constraint=models.UniqueConstraint(fields=("company", "resolution", "start_at"), name="uq_backtest_price_bar_company_resolution_start_at"),
        ),
    ]