from __future__ import annotations

from django.urls import path

from apps.api.phase3_views import (
    CompanyAnalysisSummaryView,
    PeerRankingView,
    ReportExportView,
    ScenarioAnalysisView,
)
from apps.api.phase4_views import (
    CompanyTrendView,
    ComparisonVisualsView,
    DCFValuationView,
    PortfolioActionsView,
)
from apps.api.views import (
    ChatQueryView,
    ChatSessionCollectionView,
    ChatSessionDetailView,
    ChatSessionMessagesView,
    CompanyDetailView,
    CompanyMetricsView,
    CompanySearchView,
    CompareCompaniesView,
    ComputeAnalyticsView,
    IngestCompanyView,
    JobStatusView,
    TickerUniverseSearchView,
    SystemMetricsView,
    api_root,
)
from apps.api.backtesting_views import BacktestRunDetailView, BacktestRunListView, BacktestRunView

urlpatterns = [
    path("", api_root, name="api-root"),

    # company search / lookup
    path("companies/search/", CompanySearchView.as_view(), name="company-search"),
    path("companies/search-universe/", TickerUniverseSearchView.as_view(), name="company-search-universe"),
    path("companies/ingest/", IngestCompanyView.as_view(), name="company-ingest"),
    path("companies/compare/", CompareCompaniesView.as_view(), name="company-compare"),
    path("companies/compare-visuals/", ComparisonVisualsView.as_view(), name="company-compare-visuals"),
    path("companies/peer-rank/", PeerRankingView.as_view(), name="company-peer-rank"),
    path("companies/scenario-analysis/", ScenarioAnalysisView.as_view(), name="company-scenario-analysis"),
    path("companies/dcf-valuation/", DCFValuationView.as_view(), name="company-dcf-valuation"),
    path("companies/<str:ticker>/", CompanyDetailView.as_view(), name="company-detail"),
    path("companies/<str:ticker>/metrics/", CompanyMetricsView.as_view(), name="company-metrics"),
    path("companies/<str:ticker>/analysis-summary/", CompanyAnalysisSummaryView.as_view(), name="company-analysis-summary"),
    path("companies/<str:ticker>/trends/", CompanyTrendView.as_view(), name="company-trends"),

    # analytics
    path("analytics/compute/", ComputeAnalyticsView.as_view(), name="analytics-compute"),

    # jobs
    path("jobs/<str:job_id>/", JobStatusView.as_view(), name="job-status"),

    # one-shot chat
    path("chat/query/", ChatQueryView.as_view(), name="chat-query"),

    # chat sessions
    path("chat/sessions/", ChatSessionCollectionView.as_view(), name="chat-session-collection"),
    path("chat/sessions/<str:session_id>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("chat/sessions/<str:session_id>/messages/", ChatSessionMessagesView.as_view(), name="chat-session-messages"),

    # reports
    path("reports/company/<str:ticker>/export/", ReportExportView.as_view(), name="report-export"),

    # portfolio actions
    path("portfolio/actions/", PortfolioActionsView.as_view(), name="portfolio-actions"),

        # backtesting
    path("backtests/run/", BacktestRunView.as_view(), name="backtest-run"),
    path("backtests/runs/", BacktestRunListView.as_view(), name="backtest-run-list"),
    path("backtests/runs/<str:run_id>/", BacktestRunDetailView.as_view(), name="backtest-run-detail"),
    path("ticker-universe/search/", TickerUniverseSearchView.as_view()),
    path("system/metrics/", SystemMetricsView.as_view(), name="system-metrics"),
]