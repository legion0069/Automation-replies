import pytest


def test_admin_get_settings(client):
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "keywords" in data
    assert "reply_once_days" in data


def test_admin_update_settings(client):
    update_payload = {
        "reply_once_days": 14,
        "keywords": ["link", "guide", "cheatsheet"],
    }
    response = client.post("/api/v1/settings", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["reply_once_days"] == 14
    assert data["keywords"] == ["link", "guide", "cheatsheet"]

    # Verify subsequent GET returns updated values
    get_res = client.get("/api/v1/settings")
    assert get_res.json()["reply_once_days"] == 14


def test_admin_toggle_automation(client):
    # Check current state
    initial = client.get("/api/v1/settings").json()["enabled"]

    # Toggle
    toggle_res = client.post("/api/v1/settings/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] == (not initial)

    # Toggle back
    toggle_back = client.post("/api/v1/settings/toggle")
    assert toggle_back.status_code == 200
    assert toggle_back.json()["enabled"] == initial


def test_stats_and_dashboard_endpoints(client):
    stats_res = client.get("/api/v1/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_comments" in stats
    assert "dms_sent" in stats

    dash_res = client.get("/dashboard")
    assert dash_res.status_code == 200
    assert "Instagram Auto DM Dashboard" in dash_res.text

