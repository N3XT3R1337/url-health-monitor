from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "url_health_monitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    "run-health-checks": {
        "task": "app.tasks.celery_tasks.run_scheduled_checks",
        "schedule": 30.0,
    },
    "aggregate-stats-hourly": {
        "task": "app.tasks.celery_tasks.aggregate_response_time_stats",
        "schedule": crontab(minute=0),
    },
    "cleanup-old-checks": {
        "task": "app.tasks.celery_tasks.cleanup_old_health_checks",
        "schedule": crontab(hour=3, minute=0),
    },
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def check_single_monitor(self, monitor_id: int):
    from app.database import SessionLocal
    from app.services.monitor import MonitorService
    from app.services.notification import NotificationService
    from app.models import Incident

    db = SessionLocal()
    try:
        service = MonitorService(db)
        monitor = service.get_monitor(monitor_id)
        if not monitor or not monitor.is_active:
            return {"status": "skipped", "monitor_id": monitor_id}

        previous_status = monitor.status
        health_check = service.perform_health_check(monitor_id)

        if previous_status != monitor.status:
            notification_service = NotificationService(db)
            active_incident = (
                db.query(Incident)
                .filter(
                    Incident.monitor_id == monitor_id,
                    Incident.is_resolved == False,
                )
                .first()
            )
            if active_incident and monitor.status.value == "down":
                notification_service.notify_incident_opened(active_incident, monitor)
            elif active_incident and active_incident.is_resolved:
                notification_service.notify_incident_resolved(active_incident, monitor)

        return {
            "status": "completed",
            "monitor_id": monitor_id,
            "is_healthy": health_check.is_healthy,
            "response_time_ms": health_check.response_time_ms,
        }
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task
def run_scheduled_checks():
    from app.database import SessionLocal
    from app.services.monitor import MonitorService

    db = SessionLocal()
    try:
        service = MonitorService(db)
        due_monitors = service.get_active_monitors_for_checking()
        results = []
        for monitor in due_monitors:
            task = check_single_monitor.delay(monitor.id)
            results.append({"monitor_id": monitor.id, "task_id": task.id})
        return {"scheduled": len(results), "monitors": results}
    finally:
        db.close()


@celery_app.task
def aggregate_response_time_stats():
    from datetime import datetime, timedelta
    from app.database import SessionLocal
    from app.models import Monitor, ResponseTimeStats
    from app.services.monitor import MonitorService

    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
        period_end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        period_start = period_end - timedelta(hours=1)

        for monitor in monitors:
            service = MonitorService(db)
            stats = service.calculate_stats(monitor.id, hours=1)

            if stats["total_checks"] > 0:
                stat_record = ResponseTimeStats(
                    monitor_id=monitor.id,
                    period_start=period_start,
                    period_end=period_end,
                    avg_response_time_ms=stats["avg_response_time_ms"],
                    min_response_time_ms=stats["min_response_time_ms"],
                    max_response_time_ms=stats["max_response_time_ms"],
                    p95_response_time_ms=stats["p95_response_time_ms"],
                    total_checks=stats["total_checks"],
                    successful_checks=stats["successful_checks"],
                    uptime_percentage=stats["uptime_percentage"],
                )
                db.add(stat_record)

        db.commit()
        return {"aggregated": len(monitors)}
    finally:
        db.close()


@celery_app.task
def cleanup_old_health_checks(days: int = 30):
    from datetime import datetime, timedelta
    from app.database import SessionLocal
    from app.models import HealthCheck

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = (
            db.query(HealthCheck)
            .filter(HealthCheck.checked_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted}
    finally:
        db.close()
