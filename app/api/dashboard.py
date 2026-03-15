from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Monitor, HealthCheck, Incident, MonitorStatus
from app.schemas import DashboardStats, MonitorDetailedStats, UptimeReport, HealthCheckResponse, IncidentResponse
from app.services.monitor import MonitorService
from app.services.incident import IncidentService

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Monitor.id)).scalar() or 0
    up = db.query(func.count(Monitor.id)).filter(Monitor.status == MonitorStatus.UP).scalar() or 0
    down = db.query(func.count(Monitor.id)).filter(Monitor.status == MonitorStatus.DOWN).scalar() or 0
    degraded = db.query(func.count(Monitor.id)).filter(Monitor.status == MonitorStatus.DEGRADED).scalar() or 0
    active_incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.is_resolved == False)
        .scalar() or 0
    )

    since = datetime.utcnow() - timedelta(hours=24)
    avg_rt = (
        db.query(func.avg(HealthCheck.response_time_ms))
        .filter(
            HealthCheck.checked_at >= since,
            HealthCheck.response_time_ms.isnot(None),
        )
        .scalar() or 0.0
    )

    total_checks = (
        db.query(func.count(HealthCheck.id))
        .filter(HealthCheck.checked_at >= since)
        .scalar() or 0
    )
    successful_checks = (
        db.query(func.count(HealthCheck.id))
        .filter(
            HealthCheck.checked_at >= since,
            HealthCheck.is_healthy == True,
        )
        .scalar() or 0
    )
    uptime = round((successful_checks / total_checks) * 100, 2) if total_checks > 0 else 100.0

    return DashboardStats(
        total_monitors=total,
        monitors_up=up,
        monitors_down=down,
        monitors_degraded=degraded,
        overall_uptime_percentage=uptime,
        active_incidents=active_incidents,
        avg_response_time_ms=round(float(avg_rt), 2),
    )


@router.get("/dashboard/monitors/{monitor_id}", response_model=MonitorDetailedStats)
def get_monitor_detailed_stats(
    monitor_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
):
    monitor_service = MonitorService(db)
    monitor = monitor_service.get_monitor(monitor_id)
    if not monitor:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Monitor not found")

    stats = monitor_service.calculate_stats(monitor_id, hours=hours)
    recent_checks = monitor_service.get_health_checks(monitor_id, limit=20)
    incident_service = IncidentService(db)
    active_incidents = incident_service.get_active_incidents()
    monitor_incidents = [i for i in active_incidents if i.monitor_id == monitor_id]

    return MonitorDetailedStats(
        monitor_id=monitor.id,
        monitor_name=monitor.name,
        current_status=monitor.status,
        uptime_percentage=stats["uptime_percentage"],
        avg_response_time_ms=stats["avg_response_time_ms"],
        min_response_time_ms=stats["min_response_time_ms"],
        max_response_time_ms=stats["max_response_time_ms"],
        p95_response_time_ms=stats["p95_response_time_ms"],
        total_checks=stats["total_checks"],
        successful_checks=stats["successful_checks"],
        recent_checks=[HealthCheckResponse.model_validate(c) for c in recent_checks],
        active_incidents=[IncidentResponse.model_validate(i) for i in monitor_incidents],
    )


@router.get("/dashboard/uptime-report", response_model=list[UptimeReport])
def get_uptime_report(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
):
    monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
    monitor_service = MonitorService(db)
    incident_service = IncidentService(db)
    reports = []

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(hours=hours)

    for monitor in monitors:
        stats = monitor_service.calculate_stats(monitor.id, hours=hours)
        incidents, _ = incident_service.get_incidents(monitor_id=monitor.id)
        relevant_incidents = [
            i for i in incidents
            if i.created_at >= period_start
        ]

        reports.append(UptimeReport(
            monitor_id=monitor.id,
            monitor_name=monitor.name,
            period_start=period_start,
            period_end=period_end,
            uptime_percentage=stats["uptime_percentage"],
            total_checks=stats["total_checks"],
            successful_checks=stats["successful_checks"],
            failed_checks=stats["total_checks"] - stats["successful_checks"],
            avg_response_time_ms=stats["avg_response_time_ms"],
            incidents_count=len(relevant_incidents),
        ))

    return reports


@router.get("/dashboard/status-overview")
def get_status_overview(db: Session = Depends(get_db)):
    monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
    overview = []
    for monitor in monitors:
        last_check = (
            db.query(HealthCheck)
            .filter(HealthCheck.monitor_id == monitor.id)
            .order_by(HealthCheck.checked_at.desc())
            .first()
        )
        overview.append({
            "id": monitor.id,
            "name": monitor.name,
            "url": monitor.url,
            "status": monitor.status.value if monitor.status else "unknown",
            "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
            "last_response_time_ms": last_check.response_time_ms if last_check else None,
            "last_status_code": last_check.status_code if last_check else None,
        })
    return overview


@router.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
