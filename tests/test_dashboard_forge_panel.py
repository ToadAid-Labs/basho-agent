from pathlib import Path


def test_dashboard_contains_forge_panel_hooks():
    template = Path("backend/templates/dashboard.html").read_text()

    assert "Trend Prediction Forge" in template
    assert "forge-accuracy" in template
    assert "forge-alerts-body" in template
    assert "forge-watch-body" in template
    assert "/api/ai/forge/ledger" in template
    assert "/api/ai/forge/watchlist" in template
    assert "/api/ai/forge/alerts" in template
    assert "recordForgeForecast" in template
    assert "runForgeBacktest" in template
