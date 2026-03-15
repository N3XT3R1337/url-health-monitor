from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Incident, Monitor, IncidentSeverity
from app.schemas import IncidentUpdate


class IncidentService:
    def __init__(self, db: Session):
        self.db = db

    def get_incident(self, incident_id: int) -> Optional[Incident]:
        return self.db.query(Incident).filter(Incident.id == incident_id).first()

    def get_incidents(
        self,
        monitor_id: Optional[int] = None,
        is_resolved: Optional[bool] = None,
        severity: Optional[IncidentSeverity] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Incident], int]:
        query = self.db.query(Incident)
        if monitor_id is not None:
            query = query.filter(Incident.monitor_id == monitor_id)
        if is_resolved is not None:
            query = query.filter(Incident.is_resolved == is_resolved)
        if severity is not None:
            query = query.filter(Incident.severity == severity)
        total = query.count()
        incidents = query.order_by(desc(Incident.created_at)).offset(skip).limit(limit).all()
        return incidents, total

    def get_active_incidents(self) -> List[Incident]:
        return (
            self.db.query(Incident)
            .filter(Incident.is_resolved == False)
            .order_by(desc(Incident.created_at))
            .all()
        )

    def resolve_incident(self, incident_id: int) -> Optional[Incident]:
        incident = self.get_incident(incident_id)
        if not incident:
            return None
        incident.is_resolved = True
        incident.resolved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update_incident(self, incident_id: int, data: IncidentUpdate) -> Optional[Incident]:
        incident = self.get_incident(incident_id)
        if not incident:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "is_resolved" and value is True:
                incident.is_resolved = True
                incident.resolved_at = datetime.utcnow()
            else:
                setattr(incident, field, value)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def get_incident_timeline(
        self,
        monitor_id: int,
        days: int = 30,
    ) -> List[Incident]:
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(Incident)
            .filter(
                Incident.monitor_id == monitor_id,
                Incident.created_at >= since,
            )
            .order_by(Incident.created_at)
            .all()
        )

    def get_incident_stats(self, days: int = 30) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        incidents = (
            self.db.query(Incident)
            .filter(Incident.created_at >= since)
            .all()
        )

        total = len(incidents)
        resolved = sum(1 for i in incidents if i.is_resolved)
        active = total - resolved

        resolution_times = []
        for i in incidents:
            if i.is_resolved and i.resolved_at:
                delta = (i.resolved_at - i.started_at).total_seconds()
                resolution_times.append(delta)

        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        )

        severity_counts = {}
        for sev in IncidentSeverity:
            severity_counts[sev.value] = sum(1 for i in incidents if i.severity == sev)

        return {
            "total_incidents": total,
            "active_incidents": active,
            "resolved_incidents": resolved,
            "avg_resolution_time_seconds": round(avg_resolution_time, 2),
            "severity_breakdown": severity_counts,
        }

    def bulk_resolve(self, monitor_id: int) -> int:
        active = (
            self.db.query(Incident)
            .filter(
                Incident.monitor_id == monitor_id,
                Incident.is_resolved == False,
            )
            .all()
        )
        now = datetime.utcnow()
        for incident in active:
            incident.is_resolved = True
            incident.resolved_at = now
        self.db.commit()
        return len(active)
