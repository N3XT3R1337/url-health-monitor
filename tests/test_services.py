import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models import Monitor, HealthCheck, Incident, MonitorStatus, IncidentSeverity
from app.schemas import MonitorCreate, MonitorUpdate, IncidentUpdate
from app.services.monitor import MonitorService
from app.services.incident import IncidentService


class TestMonitorService:
    def test_create_monitor(self, db_session):
        service = MonitorService(db_session)
        data = MonitorCreate(
            name="Service Test",
            url="https://example.com",
            method="GET",
        )
        monitor = service.create_monitor(data)
        assert monitor.id is not None
        assert monitor.name == "Service Test"

    def test_get_monitors_pagination(self, db_session):
        service = MonitorService(db_session)
        for i in range(5):
            service.create_monitor(MonitorCreate(
                name=f"Monitor {i}",
                url=f"https://example{i}.com",
            ))

        monitors, total = service.get_monitors(skip=0, limit=3)
        assert total == 5
        assert len(monitors) == 3

    def test_update_monitor(self, db_session):
        service = MonitorService(db_session)
        monitor = service.create_monitor(MonitorCreate(
            name="Original",
            url="https://example.com",
        ))
        updated = service.update_monitor(
            monitor.id,
            MonitorUpdate(name="Updated Name"),
        )
        assert updated.name == "Updated Name"

    def test_delete_monitor(self, db_session):
        service = MonitorService(db_session)
        monitor = service.create_monitor(MonitorCreate(
            name="Delete Me",
            url="https://example.com",
        ))
        assert service.delete_monitor(monitor.id) is True
        assert service.get_monitor(monitor.id) is None

    def test_toggle_monitor(self, db_session):
        service = MonitorService(db_session)
        monitor = service.create_monitor(MonitorCreate(
            name="Toggle",
            url="https://example.com",
        ))
        toggled = service.toggle_monitor(monitor.id)
        assert toggled.is_active is False
        toggled = service.toggle_monitor(monitor.id)
        assert toggled.is_active is True

    def test_calculate_stats_empty(self, db_session):
        service = MonitorService(db_session)
        monitor = service.create_monitor(MonitorCreate(
            name="Stats",
            url="https://example.com",
        ))
        stats = service.calculate_stats(monitor.id)
        assert stats["total_checks"] == 0
        assert stats["uptime_percentage"] == 0.0

    def test_calculate_stats_with_data(self, db_session):
        service = MonitorService(db_session)
        monitor = service.create_monitor(MonitorCreate(
            name="Stats Data",
            url="https://example.com",
        ))

        for i in range(10):
            check = HealthCheck(
                monitor_id=monitor.id,
                status_code=200,
                response_time_ms=100.0 + i * 10,
                is_healthy=True,
                checked_at=datetime.utcnow() - timedelta(minutes=i),
            )
            db_session.add(check)
        db_session.commit()

        stats = service.calculate_stats(monitor.id)
        assert stats["total_checks"] == 10
        assert stats["successful_checks"] == 10
        assert stats["uptime_percentage"] == 100.0
        assert stats["avg_response_time_ms"] > 0

    def test_active_monitors_for_checking(self, db_session):
        service = MonitorService(db_session)
        m1 = service.create_monitor(MonitorCreate(
            name="Due",
            url="https://example.com",
            check_interval=60,
        ))
        m2 = service.create_monitor(MonitorCreate(
            name="Not Due",
            url="https://example2.com",
            check_interval=60,
        ))
        m2.last_checked_at = datetime.utcnow()
        db_session.commit()

        due = service.get_active_monitors_for_checking()
        assert any(m.id == m1.id for m in due)

    def test_bulk_create(self, db_session):
        service = MonitorService(db_session)
        monitors_data = [
            MonitorCreate(name=f"Bulk {i}", url=f"https://bulk{i}.com")
            for i in range(3)
        ]
        created = service.bulk_create_monitors(monitors_data)
        assert len(created) == 3


class TestIncidentService:
    def test_get_active_incidents(self, db_session):
        monitor = Monitor(name="Incident Monitor", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        incident = Incident(
            monitor_id=monitor.id,
            title="Active Incident",
            severity=IncidentSeverity.HIGH,
        )
        db_session.add(incident)
        db_session.commit()

        service = IncidentService(db_session)
        active = service.get_active_incidents()
        assert len(active) == 1

    def test_resolve_incident(self, db_session):
        monitor = Monitor(name="Resolve Test", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        incident = Incident(
            monitor_id=monitor.id,
            title="To Resolve",
        )
        db_session.add(incident)
        db_session.commit()

        service = IncidentService(db_session)
        resolved = service.resolve_incident(incident.id)
        assert resolved.is_resolved is True
        assert resolved.resolved_at is not None

    def test_incident_stats(self, db_session):
        monitor = Monitor(name="Stats Monitor", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        for i in range(3):
            incident = Incident(
                monitor_id=monitor.id,
                title=f"Incident {i}",
                severity=IncidentSeverity.MEDIUM,
            )
            db_session.add(incident)
        db_session.commit()

        service = IncidentService(db_session)
        stats = service.get_incident_stats()
        assert stats["total_incidents"] == 3
        assert stats["active_incidents"] == 3

    def test_bulk_resolve(self, db_session):
        monitor = Monitor(name="Bulk Resolve", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        for i in range(3):
            db_session.add(Incident(
                monitor_id=monitor.id,
                title=f"Incident {i}",
            ))
        db_session.commit()

        service = IncidentService(db_session)
        count = service.bulk_resolve(monitor.id)
        assert count == 3
        assert len(service.get_active_incidents()) == 0

    def test_update_incident(self, db_session):
        monitor = Monitor(name="Update Inc", url="https://test.com")
        db_session.add(monitor)
        db_session.commit()

        incident = Incident(
            monitor_id=monitor.id,
            title="Update Me",
            severity=IncidentSeverity.LOW,
        )
        db_session.add(incident)
        db_session.commit()

        service = IncidentService(db_session)
        updated = service.update_incident(
            incident.id,
            IncidentUpdate(severity=IncidentSeverity.CRITICAL),
        )
        assert updated.severity == IncidentSeverity.CRITICAL
