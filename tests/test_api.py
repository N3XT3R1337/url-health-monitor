import pytest
from fastapi.testclient import TestClient


class TestMonitorAPI:
    def test_create_monitor(self, client, sample_monitor_data):
        response = client.post("/api/v1/monitors", json=sample_monitor_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_monitor_data["name"]
        assert data["url"] == sample_monitor_data["url"]
        assert data["is_active"] is True
        assert data["status"] == "unknown"

    def test_get_monitor(self, client, created_monitor):
        monitor_id = created_monitor["id"]
        response = client.get(f"/api/v1/monitors/{monitor_id}")
        assert response.status_code == 200
        assert response.json()["id"] == monitor_id

    def test_get_monitor_not_found(self, client):
        response = client.get("/api/v1/monitors/999")
        assert response.status_code == 404

    def test_list_monitors(self, client, created_monitor):
        response = client.get("/api/v1/monitors")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_update_monitor(self, client, created_monitor):
        monitor_id = created_monitor["id"]
        response = client.put(
            f"/api/v1/monitors/{monitor_id}",
            json={"name": "Updated Monitor"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Monitor"

    def test_delete_monitor(self, client, created_monitor):
        monitor_id = created_monitor["id"]
        response = client.delete(f"/api/v1/monitors/{monitor_id}")
        assert response.status_code == 204
        response = client.get(f"/api/v1/monitors/{monitor_id}")
        assert response.status_code == 404

    def test_toggle_monitor(self, client, created_monitor):
        monitor_id = created_monitor["id"]
        response = client.post(f"/api/v1/monitors/{monitor_id}/toggle")
        assert response.status_code == 200
        assert response.json()["is_active"] is False
        response = client.post(f"/api/v1/monitors/{monitor_id}/toggle")
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_create_monitor_validation(self, client):
        response = client.post("/api/v1/monitors", json={"name": "", "url": ""})
        assert response.status_code == 422

    def test_bulk_create_monitors(self, client):
        data = {
            "monitors": [
                {"name": "Monitor 1", "url": "https://example.com", "method": "GET"},
                {"name": "Monitor 2", "url": "https://example.org", "method": "GET"},
            ]
        }
        response = client.post("/api/v1/monitors/bulk", json=data)
        assert response.status_code == 201
        assert len(response.json()) == 2


class TestDashboardAPI:
    def test_dashboard_stats(self, client):
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_monitors" in data
        assert "monitors_up" in data
        assert "overall_uptime_percentage" in data

    def test_health_check_endpoint(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_status_overview(self, client, created_monitor):
        response = client.get("/api/v1/dashboard/status-overview")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_uptime_report(self, client):
        response = client.get("/api/v1/dashboard/uptime-report")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestIncidentAPI:
    def test_list_incidents(self, client):
        response = client.get("/api/v1/incidents")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data

    def test_incident_stats(self, client):
        response = client.get("/api/v1/incidents/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data
        assert "severity_breakdown" in data

    def test_get_incident_not_found(self, client):
        response = client.get("/api/v1/incidents/999")
        assert response.status_code == 404


class TestNotificationAPI:
    def test_add_notification_channel(self, client, created_monitor):
        monitor_id = created_monitor["id"]
        data = {
            "channel_type": "slack",
            "webhook_url": "https://hooks.slack.com/test",
        }
        response = client.post(f"/api/v1/monitors/{monitor_id}/notifications", json=data)
        assert response.status_code == 201
        assert response.json()["channel_type"] == "slack"

    def test_add_notification_monitor_not_found(self, client):
        data = {
            "channel_type": "slack",
            "webhook_url": "https://hooks.slack.com/test",
        }
        response = client.post("/api/v1/monitors/999/notifications", json=data)
        assert response.status_code == 404
