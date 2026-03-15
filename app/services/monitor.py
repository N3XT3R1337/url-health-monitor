import json
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models import (
    Monitor, HealthCheck, MonitorStatus,
    ResponseTimeStats, Incident, IncidentSeverity,
)
from app.schemas import MonitorCreate, MonitorUpdate
from app.config import settings


class MonitorService:
    def __init__(self, db: Session):
        self.db = db

    def create_monitor(self, data: MonitorCreate) -> Monitor:
        monitor = Monitor(
            name=data.name,
            url=data.url,
            method=data.method,
            headers=data.headers or "{}",
            body=data.body,
            expected_status_code=data.expected_status_code,
            check_interval=data.check_interval,
            timeout=data.timeout,
        )
        self.db.add(monitor)
        self.db.commit()
        self.db.refresh(monitor)

        if data.notification_channels:
            from app.models import NotificationChannel
            for ch in data.notification_channels:
                channel = NotificationChannel(
                    monitor_id=monitor.id,
                    channel_type=ch.channel_type,
                    webhook_url=ch.webhook_url,
                    email_address=ch.email_address,
                    is_active=ch.is_active,
                )
                self.db.add(channel)
            self.db.commit()
            self.db.refresh(monitor)

        return monitor

    def get_monitor(self, monitor_id: int) -> Optional[Monitor]:
        return self.db.query(Monitor).filter(Monitor.id == monitor_id).first()

    def get_monitors(
        self,
        skip: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None,
        status: Optional[MonitorStatus] = None,
    ) -> Tuple[List[Monitor], int]:
        query = self.db.query(Monitor)
        if is_active is not None:
            query = query.filter(Monitor.is_active == is_active)
        if status is not None:
            query = query.filter(Monitor.status == status)
        total = query.count()
        monitors = query.order_by(desc(Monitor.created_at)).offset(skip).limit(limit).all()
        return monitors, total

    def update_monitor(self, monitor_id: int, data: MonitorUpdate) -> Optional[Monitor]:
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(monitor, field, value)
        monitor.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(monitor)
        return monitor

    def delete_monitor(self, monitor_id: int) -> bool:
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            return False
        self.db.delete(monitor)
        self.db.commit()
        return True

    def toggle_monitor(self, monitor_id: int) -> Optional[Monitor]:
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            return None
        monitor.is_active = not monitor.is_active
        monitor.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(monitor)
        return monitor

    def perform_health_check(self, monitor_id: int) -> HealthCheck:
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            raise ValueError(f"Monitor {monitor_id} not found")

        health_check = HealthCheck(monitor_id=monitor.id)
        headers = {}
        try:
            headers = json.loads(monitor.headers) if monitor.headers else {}
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            start_time = time.time()
            with httpx.Client(timeout=monitor.timeout, follow_redirects=True) as client:
                response = client.request(
                    method=monitor.method,
                    url=monitor.url,
                    headers=headers,
                    content=monitor.body if monitor.body else None,
                )
            elapsed_ms = (time.time() - start_time) * 1000

            health_check.status_code = response.status_code
            health_check.response_time_ms = round(elapsed_ms, 2)
            health_check.is_healthy = response.status_code == monitor.expected_status_code
            health_check.checked_at = datetime.utcnow()

            if health_check.is_healthy and elapsed_ms > settings.RESPONSE_TIME_WARNING_MS:
                monitor.status = MonitorStatus.DEGRADED
            elif health_check.is_healthy:
                monitor.status = MonitorStatus.UP
            else:
                health_check.error_message = f"Expected {monitor.expected_status_code}, got {response.status_code}"
                monitor.status = MonitorStatus.DOWN

        except httpx.TimeoutException:
            health_check.is_healthy = False
            health_check.error_message = "Request timed out"
            health_check.checked_at = datetime.utcnow()
            monitor.status = MonitorStatus.DOWN

        except httpx.ConnectError as e:
            health_check.is_healthy = False
            health_check.error_message = f"Connection error: {str(e)[:500]}"
            health_check.checked_at = datetime.utcnow()
            monitor.status = MonitorStatus.DOWN

        except Exception as e:
            health_check.is_healthy = False
            health_check.error_message = f"Unexpected error: {str(e)[:500]}"
            health_check.checked_at = datetime.utcnow()
            monitor.status = MonitorStatus.DOWN

        monitor.last_checked_at = health_check.checked_at
        self.db.add(health_check)
        self.db.commit()
        self.db.refresh(health_check)

        self._handle_incident_detection(monitor, health_check)

        return health_check

    def _handle_incident_detection(self, monitor: Monitor, health_check: HealthCheck):
        if not health_check.is_healthy:
            recent_checks = (
                self.db.query(HealthCheck)
                .filter(HealthCheck.monitor_id == monitor.id)
                .order_by(desc(HealthCheck.checked_at))
                .limit(settings.INCIDENT_THRESHOLD)
                .all()
            )
            consecutive_failures = sum(1 for c in recent_checks if not c.is_healthy)

            if consecutive_failures >= settings.INCIDENT_THRESHOLD:
                active_incident = (
                    self.db.query(Incident)
                    .filter(
                        Incident.monitor_id == monitor.id,
                        Incident.is_resolved == False,
                    )
                    .first()
                )

                if not active_incident:
                    severity = IncidentSeverity.MEDIUM
                    if consecutive_failures >= settings.INCIDENT_THRESHOLD * 3:
                        severity = IncidentSeverity.CRITICAL
                    elif consecutive_failures >= settings.INCIDENT_THRESHOLD * 2:
                        severity = IncidentSeverity.HIGH

                    incident = Incident(
                        monitor_id=monitor.id,
                        title=f"{monitor.name} is down",
                        description=health_check.error_message,
                        severity=severity,
                        consecutive_failures=consecutive_failures,
                    )
                    self.db.add(incident)
                    self.db.commit()
                else:
                    active_incident.consecutive_failures = consecutive_failures
                    if consecutive_failures >= settings.INCIDENT_THRESHOLD * 3:
                        active_incident.severity = IncidentSeverity.CRITICAL
                    elif consecutive_failures >= settings.INCIDENT_THRESHOLD * 2:
                        active_incident.severity = IncidentSeverity.HIGH
                    self.db.commit()
        else:
            active_incident = (
                self.db.query(Incident)
                .filter(
                    Incident.monitor_id == monitor.id,
                    Incident.is_resolved == False,
                )
                .first()
            )
            if active_incident:
                active_incident.is_resolved = True
                active_incident.resolved_at = datetime.utcnow()
                self.db.commit()

    def get_health_checks(
        self,
        monitor_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[HealthCheck]:
        return (
            self.db.query(HealthCheck)
            .filter(HealthCheck.monitor_id == monitor_id)
            .order_by(desc(HealthCheck.checked_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_response_time_history(
        self,
        monitor_id: int,
        hours: int = 24,
    ) -> List[HealthCheck]:
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(HealthCheck)
            .filter(
                HealthCheck.monitor_id == monitor_id,
                HealthCheck.checked_at >= since,
                HealthCheck.response_time_ms.isnot(None),
            )
            .order_by(HealthCheck.checked_at)
            .all()
        )

    def calculate_stats(self, monitor_id: int, hours: int = 24) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        checks = (
            self.db.query(HealthCheck)
            .filter(
                HealthCheck.monitor_id == monitor_id,
                HealthCheck.checked_at >= since,
            )
            .all()
        )

        if not checks:
            return {
                "total_checks": 0,
                "successful_checks": 0,
                "uptime_percentage": 0.0,
                "avg_response_time_ms": 0.0,
                "min_response_time_ms": 0.0,
                "max_response_time_ms": 0.0,
                "p95_response_time_ms": 0.0,
            }

        total = len(checks)
        successful = sum(1 for c in checks if c.is_healthy)
        response_times = [c.response_time_ms for c in checks if c.response_time_ms is not None]

        avg_rt = sum(response_times) / len(response_times) if response_times else 0.0
        min_rt = min(response_times) if response_times else 0.0
        max_rt = max(response_times) if response_times else 0.0

        sorted_rt = sorted(response_times)
        p95_idx = int(len(sorted_rt) * 0.95)
        p95_rt = sorted_rt[min(p95_idx, len(sorted_rt) - 1)] if sorted_rt else 0.0

        return {
            "total_checks": total,
            "successful_checks": successful,
            "uptime_percentage": round((successful / total) * 100, 2) if total > 0 else 0.0,
            "avg_response_time_ms": round(avg_rt, 2),
            "min_response_time_ms": round(min_rt, 2),
            "max_response_time_ms": round(max_rt, 2),
            "p95_response_time_ms": round(p95_rt, 2),
        }

    def get_active_monitors_for_checking(self) -> List[Monitor]:
        now = datetime.utcnow()
        monitors = (
            self.db.query(Monitor)
            .filter(Monitor.is_active == True)
            .all()
        )
        due_monitors = []
        for monitor in monitors:
            if monitor.last_checked_at is None:
                due_monitors.append(monitor)
            elif (now - monitor.last_checked_at).total_seconds() >= monitor.check_interval:
                due_monitors.append(monitor)
        return due_monitors

    def bulk_create_monitors(self, monitors_data: List[MonitorCreate]) -> List[Monitor]:
        created = []
        for data in monitors_data:
            monitor = self.create_monitor(data)
            created.append(monitor)
        return created
