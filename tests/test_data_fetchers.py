"""Tests for the data_fetchers module."""

import pytest
from app.data_fetchers import (
    YahooFinanceFetcher,
    RSSFetcher,
    get_fetcher,
    _safe_float,
)
from app.trigger_conditions import FINANCIAL_METRICS


class TestSafeFloat:
    """Test _safe_float helper."""

    def test_safe_float_valid(self):
        assert _safe_float(100) == 100.0
        assert _safe_float("100.5") == 100.5
        assert _safe_float(0) == 0.0

    def test_safe_float_invalid(self):
        assert _safe_float(None) is None
        assert _safe_float("invalid") is None
        assert _safe_float("") is None


class TestYahooFinanceFetcher:
    """Test YahooFinanceFetcher."""

    def test_fetcher_initialization(self):
        fetcher = YahooFinanceFetcher()
        assert fetcher.cache == {}

    def test_fetch_financials_no_ticker(self):
        fetcher = YahooFinanceFetcher()
        result = fetcher.fetch_financials("")
        assert "error" in result
        assert "No ticker" in result["error"]

    def test_fetch_financials_invalid_ticker(self):
        fetcher = YahooFinanceFetcher()
        result = fetcher.fetch_financials("INVALID_TICKER_12345")
        # May return error or empty data
        assert "error" in result or result.get("metrics") is not None

    def test_fetch_price_no_ticker(self):
        fetcher = YahooFinanceFetcher()
        result = fetcher.fetch_price("")
        assert "error" in result
        assert "No ticker" in result["error"]

    def test_fetch_price_structure(self):
        fetcher = YahooFinanceFetcher()
        # This requires network - test structure if available
        result = fetcher.fetch_price("AAPL")
        if "error" not in result:
            assert "ticker" in result
            assert "price" in result
            assert "previous_close" in result
            assert "currency" in result

    def test_fetch_historical_metric(self):
        fetcher = YahooFinanceFetcher()
        result = fetcher.fetch_historical_metric("AAPL", "revenue_growth_ttm")
        # Returns list of floats or empty list
        assert isinstance(result, list)


class TestRSSFetcher:
    """Test RSSFetcher."""

    def test_fetcher_initialization(self):
        fetcher = RSSFetcher()
        assert fetcher.cache == {}

    def test_classify_impact(self):
        fetcher = RSSFetcher()
        assert fetcher._classify_impact("Company reports strong profit growth") == "Positive"
        assert fetcher._classify_impact("Stock falls on loss") == "Negative"
        assert fetcher._classify_impact("Acquisition announced") == "Positive"
        assert fetcher._classify_impact("Bankruptcy filing") == "Negative"
        assert fetcher._classify_impact("Annual meeting scheduled") == "Neutral"

    def test_fetch_google_news(self):
        fetcher = RSSFetcher()
        result = fetcher.fetch_google_news("Apple", limit=5)
        assert isinstance(result, list)
        if len(result) > 0 and "error" not in result[0]:
            assert "title" in result[0]
            assert "url" in result[0]
            assert "source" in result[0]
            assert "impact" in result[0]

    def test_fetch_yahoo_rss(self):
        fetcher = RSSFetcher()
        result = fetcher.fetch_yahoo_rss("AAPL", limit=5)
        assert isinstance(result, list)

    def test_fetch_company_news(self):
        fetcher = RSSFetcher()
        result = fetcher.fetch_company_news("Apple", limit=5)
        assert isinstance(result, list)

    def test_fetch_competitor_news(self):
        fetcher = RSSFetcher()
        result = fetcher.fetch_competitor_news(["Microsoft", "Google"], "Technology", limit=5)
        assert isinstance(result, list)

    def test_fetch_regulatory_news(self):
        fetcher = RSSFetcher()
        result = fetcher.fetch_regulatory_news("Apple", "Technology", limit=5)
        assert isinstance(result, list)


class TestGetFetcher:
    """Test get_fetcher factory function."""

    def test_get_fetcher_financials(self):
        fetcher = get_fetcher("yahoo_finance_financials")
        assert isinstance(fetcher, YahooFinanceFetcher)

    def test_get_fetcher_google_news(self):
        fetcher = get_fetcher("google_news_rss")
        assert isinstance(fetcher, RSSFetcher)

    def test_get_fetcher_yahoo_rss(self):
        fetcher = get_fetcher("yahoo_finance_rss")
        assert isinstance(fetcher, RSSFetcher)

    def test_get_fetcher_price(self):
        fetcher = get_fetcher("yahoo_finance_price")
        assert isinstance(fetcher, YahooFinanceFetcher)

    def test_get_fetcher_unknown(self):
        with pytest.raises(ValueError, match="Unknown data source"):
            get_fetcher("unknown_source")


class TestFinancialMetrics:
    """Test financial metrics configuration."""

    def test_financial_metrics_structure(self):
        # Verify all expected metrics are defined
        expected_metrics = [
            "revenue_growth_ttm",
            "operating_margin_ttm",
            "gross_margin_ttm",
            "net_debt_ttm",
            "fcf_ttm",
            "eps_ttm",
            "debt_to_equity_ttm",
            "debt_to_assets_ttm",
            "revenue_ttm",
            "operating_income_ttm",
            "net_income_ttm",
            "cash_ttm",
            "working_capital_ttm",
            "ebitda_margin_ttm",
            "fcf_margin_ttm",
            "fcf_conversion_ttm",
        ]

        for metric in expected_metrics:
            assert metric in FINANCIAL_METRICS
            assert "unit" in FINANCIAL_METRICS[metric]
            assert "source" in FINANCIAL_METRICS[metric]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])