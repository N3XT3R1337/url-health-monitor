import pytest
from datetime import datetime

from app.models import Monitor, HealthCheck, Incident, NotificationChannel, MonitorStatus, IncidentSeverity, NotificationType
from app.database import Base


class TestMonitorModel:
    def test_create_monitor(self, db_session):
        monitor = Monitor(
            name="Test Site",
            url="https://example.com",
            method="GET",
            expected_status_code=200,
            check_interval=60,
            timeout=30,
        )
        db_session.add(monitor)
        db_session.commit()
        db_session.refresh(monitor)

        assert monitor.id is not None
        assert monitor.name == "Test Site"
        assert monitor.is_active is True
        assert monitor.status == MonitorStatus.UNKNOWN

    def test_monitor_defaults(self, db_session):
        monitor = Monitor(name="Defaults", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        assert monitor.method == "GET"
        assert monitor.expected_status_code == 200
        assert monitor.check_interval == 60
        assert monitor.timeout == 30
        assert monitor.is_active is True

    def test_health_check_relationship(self, db_session):
        monitor = Monitor(name="Related", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        check = HealthCheck(
            monitor_id=monitor.id,
            status_code=200,
            response_time_ms=150.5,
            is_healthy=True,
        )
        db_session.add(check)
        db_session.commit()

        assert len(monitor.checks) == 1
        assert monitor.checks[0].status_code == 200

    def test_incident_creation(self, db_session):
        monitor = Monitor(name="Incident Test", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        incident = Incident(
            monitor_id=monitor.id,
            title="Site is down",
            severity=IncidentSeverity.HIGH,
        )
        db_session.add(incident)
        db_session.commit()

        assert incident.id is not None
        assert incident.is_resolved is False
        assert incident.severity == IncidentSeverity.HIGH

    def test_notification_channel(self, db_session):
        monitor = Monitor(name="Notify Test", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        channel = NotificationChannel(
            monitor_id=monitor.id,
            channel_type=NotificationType.SLACK,
            webhook_url="https://hooks.slack.com/test",
        )
        db_session.add(channel)
        db_session.commit()

        assert channel.id is not None
        assert channel.channel_type == NotificationType.SLACK
        assert len(monitor.notification_channels) == 1

    def test_cascade_delete(self, db_session):
        monitor = Monitor(name="Cascade", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        check = HealthCheck(monitor_id=monitor.id, is_healthy=True)
        incident = Incident(monitor_id=monitor.id, title="Down")
        db_session.add_all([check, incident])
        db_session.commit()

        db_session.delete(monitor)
        db_session.commit()

        assert db_session.query(HealthCheck).count() == 0
        assert db_session.query(Incident).count() == 0
