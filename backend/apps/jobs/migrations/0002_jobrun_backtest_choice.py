from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobrun",
            name="job_type",
            field=models.CharField(
                choices=[
                    ("company_sync", "Company Sync"),
                    ("financial_ingestion", "Financial Ingestion"),
                    ("analytics_compute", "Analytics Compute"),
                    ("valuation", "Valuation"),
                    ("chat_analysis", "Chat Analysis"),
                    ("report_generation", "Report Generation"),
                    ("backtest", "Backtest"),
                ],
                max_length=64,
            ),
        ),
    ]