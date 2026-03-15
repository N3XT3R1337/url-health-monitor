from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MonitorStatus, IncidentSeverity, NotificationType
from app.schemas import (
    MonitorCreate, MonitorUpdate, MonitorResponse,
    HealthCheckResponse, IncidentResponse, IncidentUpdate,
    NotificationChannelCreate, NotificationChannelResponse,
    BulkMonitorCreate, PaginatedResponse,
)
from app.services.monitor import MonitorService
from app.services.incident import IncidentService
from app.services.notification import NotificationService

router = APIRouter()


@router.post("/monitors", response_model=MonitorResponse, status_code=201)
def create_monitor(data: MonitorCreate, db: Session = Depends(get_db)):
    service = MonitorService(db)
    monitor = service.create_monitor(data)
    return monitor


@router.get("/monitors", response_model=PaginatedResponse)
def list_monitors(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    status: Optional[MonitorStatus] = None,
    db: Session = Depends(get_db),
):
    service = MonitorService(db)
    skip = (page - 1) * per_page
    monitors, total = service.get_monitors(skip=skip, limit=per_page, is_active=is_active, status=status)
    pages = (total + per_page - 1) // per_page if total > 0 else 1
    return PaginatedResponse(
        items=[MonitorResponse.model_validate(m) for m in monitors],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/monitors/{monitor_id}", response_model=MonitorResponse)
def get_monitor(monitor_id: int, db: Session = Depends(get_db)):
    service = MonitorService(db)
    monitor = service.get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.put("/monitors/{monitor_id}", response_model=MonitorResponse)
def update_monitor(monitor_id: int, data: MonitorUpdate, db: Session = Depends(get_db)):
    service = MonitorService(db)
    monitor = service.update_monitor(monitor_id, data)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    service = MonitorService(db)
    if not service.delete_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")


@router.post("/monitors/{monitor_id}/toggle", response_model=MonitorResponse)
def toggle_monitor(monitor_id: int, db: Session = Depends(get_db)):
    service = MonitorService(db)
    monitor = service.toggle_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.post("/monitors/{monitor_id}/check", response_model=HealthCheckResponse)
def trigger_health_check(monitor_id: int, db: Session = Depends(get_db)):
    service = MonitorService(db)
    try:
        check = service.perform_health_check(monitor_id)
        return check
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/monitors/{monitor_id}/checks", response_model=list[HealthCheckResponse])
def get_health_checks(
    monitor_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = MonitorService(db)
    monitor = service.get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    checks = service.get_health_checks(monitor_id, limit=limit, offset=offset)
    return checks


@router.get("/monitors/{monitor_id}/response-times")
def get_response_times(
    monitor_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
):
    service = MonitorService(db)
    monitor = service.get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    checks = service.get_response_time_history(monitor_id, hours=hours)
    return [
        {
            "checked_at": c.checked_at.isoformat(),
            "response_time_ms": c.response_time_ms,
            "is_healthy": c.is_healthy,
        }
        for c in checks
    ]


@router.get("/monitors/{monitor_id}/stats")
def get_monitor_stats(
    monitor_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
):
    service = MonitorService(db)
    monitor = service.get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    stats = service.calculate_stats(monitor_id, hours=hours)
    stats["monitor_id"] = monitor_id
    stats["monitor_name"] = monitor.name
    stats["current_status"] = monitor.status.value if monitor.status else "unknown"
    return stats


@router.post("/monitors/bulk", response_model=list[MonitorResponse], status_code=201)
def bulk_create_monitors(data: BulkMonitorCreate, db: Session = Depends(get_db)):
    service = MonitorService(db)
    monitors = service.bulk_create_monitors(data.monitors)
    return monitors


@router.get("/incidents", response_model=PaginatedResponse)
def list_incidents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    monitor_id: Optional[int] = None,
    is_resolved: Optional[bool] = None,
    severity: Optional[IncidentSeverity] = None,
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    skip = (page - 1) * per_page
    incidents, total = service.get_incidents(
        monitor_id=monitor_id,
        is_resolved=is_resolved,
        severity=severity,
        skip=skip,
        limit=per_page,
    )
    pages = (total + per_page - 1) // per_page if total > 0 else 1
    return PaginatedResponse(
        items=[IncidentResponse.model_validate(i) for i in incidents],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    service = IncidentService(db)
    incident = service.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.put("/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, data: IncidentUpdate, db: Session = Depends(get_db)):
    service = IncidentService(db)
    incident = service.update_incident(incident_id, data)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    service = IncidentService(db)
    incident = service.resolve_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/incidents/active/all", response_model=list[IncidentResponse])
def get_active_incidents(db: Session = Depends(get_db)):
    service = IncidentService(db)
    return service.get_active_incidents()


@router.get("/monitors/{monitor_id}/incidents/timeline", response_model=list[IncidentResponse])
def get_incident_timeline(
    monitor_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    return service.get_incident_timeline(monitor_id, days=days)


@router.post("/monitors/{monitor_id}/incidents/resolve-all")
def bulk_resolve_incidents(monitor_id: int, db: Session = Depends(get_db)):
    service = IncidentService(db)
    count = service.bulk_resolve(monitor_id)
    return {"resolved_count": count}


@router.get("/incidents/stats")
def get_incident_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    return service.get_incident_stats(days=days)


@router.post("/monitors/{monitor_id}/notifications", response_model=NotificationChannelResponse, status_code=201)
def add_notification_channel(
    monitor_id: int,
    data: NotificationChannelCreate,
    db: Session = Depends(get_db),
):
    monitor_service = MonitorService(db)
    monitor = monitor_service.get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    notification_service = NotificationService(db)
    channel = notification_service.add_channel(
        monitor_id=monitor_id,
        channel_type=data.channel_type,
        webhook_url=data.webhook_url,
        email_address=data.email_address,
    )
    return channel


@router.delete("/notifications/{channel_id}", status_code=204)
def remove_notification_channel(channel_id: int, db: Session = Depends(get_db)):
    service = NotificationService(db)
    if not service.remove_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")


@router.post("/notifications/{channel_id}/toggle", response_model=NotificationChannelResponse)
def toggle_notification_channel(channel_id: int, db: Session = Depends(get_db)):
    service = NotificationService(db)
    channel = service.toggle_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel
