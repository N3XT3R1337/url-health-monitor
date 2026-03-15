```
 ██╗   ██╗██████╗ ██╗         ██╗  ██╗███████╗ █████╗ ██╗  ████████╗██╗  ██╗
 ██║   ██║██╔══██╗██║         ██║  ██║██╔════╝██╔══██╗██║  ╚══██╔══╝██║  ██║
 ██║   ██║██████╔╝██║         ███████║█████╗  ███████║██║     ██║   ███████║
 ██║   ██║██╔══██╗██║         ██╔══██║██╔══╝  ██╔══██║██║     ██║   ██╔══██║
 ╚██████╔╝██║  ██║███████╗    ██║  ██║███████╗██║  ██║███████╗██║   ██║  ██║
  ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝  ╚═╝
 ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗
 ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗
 ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝
 ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗
 ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║
 ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
```

![Build](https://img.shields.io/github/actions/workflow/status/N3XT3R1337/url-health-monitor/ci.yml?style=flat-square)
![License](https://img.shields.io/github/license/N3XT3R1337/url-health-monitor?style=flat-square)
![Python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=flat-square&logo=redis&logoColor=white)

Website uptime monitoring service with cron-based health checks, webhook notifications (Slack, Discord, email), status dashboard API, response time tracking, and incident history.

---

## Features

- **Automated Health Checks** — Cron-based monitoring with configurable intervals per URL
- **Multi-Channel Notifications** — Slack, Discord, and email alerts on incidents
- **Response Time Tracking** — Detailed latency metrics with P95, min, max, and averages
- **Incident Management** — Automatic detection, severity escalation, and resolution tracking
- **Status Dashboard API** — Real-time overview, uptime reports, and per-monitor detailed stats
- **Bulk Operations** — Create multiple monitors and resolve incidents in batch
- **Celery Task Queue** — Background workers for non-blocking health checks
- **Hourly Aggregation** — Automatic response time stats rolled up every hour
- **Auto-Cleanup** — Old health check records purged automatically after 30 days

---

## Tech Stack

| Component       | Technology              |
|-----------------|-------------------------|
| API Framework   | FastAPI                 |
| Task Queue      | Celery                  |
| Message Broker  | Redis                   |
| ORM             | SQLAlchemy 2.0          |
| HTTP Client     | httpx                   |
| Validation      | Pydantic v2             |
| Database        | SQLite (default) / PostgreSQL |
| Containerization| Docker & Docker Compose |

---

## Installation

### Prerequisites

- Python 3.12+
- Redis (for Celery task queue)
- Docker & Docker Compose (optional)

### Local Setup

```bash
git clone https://github.com/N3XT3R1337/url-health-monitor.git
cd url-health-monitor

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

Start the API server:

```bash
uvicorn app.main:app --reload --port 8000
```

Start the Celery worker (separate terminal):

```bash
celery -A app.tasks.celery_tasks worker --loglevel=info
```

Start the Celery beat scheduler (separate terminal):

```bash
celery -A app.tasks.celery_tasks beat --loglevel=info
```

### Docker Setup

```bash
docker compose up -d
```

This starts the API, Celery worker, Celery beat, and Redis.

---

## Usage

### Create a Monitor

```bash
curl -X POST http://localhost:8000/api/v1/monitors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub",
    "url": "https://github.com",
    "method": "GET",
    "expected_status_code": 200,
    "check_interval": 120,
    "notification_channels": [
      {
        "channel_type": "slack",
        "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
      }
    ]
  }'
```

### Trigger a Manual Check

```bash
curl -X POST http://localhost:8000/api/v1/monitors/1/check
```

### Get Dashboard Stats

```bash
curl http://localhost:8000/api/v1/dashboard/stats
```

```json
{
  "total_monitors": 5,
  "monitors_up": 4,
  "monitors_down": 1,
  "monitors_degraded": 0,
  "overall_uptime_percentage": 99.72,
  "active_incidents": 1,
  "avg_response_time_ms": 245.8
}
```

### View Response Time History

```bash
curl http://localhost:8000/api/v1/monitors/1/response-times?hours=48
```

### List Active Incidents

```bash
curl http://localhost:8000/api/v1/incidents/active/all
```

### Resolve an Incident

```bash
curl -X POST http://localhost:8000/api/v1/incidents/1/resolve
```

### Bulk Create Monitors

```bash
curl -X POST http://localhost:8000/api/v1/monitors/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "monitors": [
      {"name": "Google", "url": "https://google.com"},
      {"name": "GitHub", "url": "https://github.com"},
      {"name": "Reddit", "url": "https://reddit.com"}
    ]
  }'
```

### Get Uptime Report

```bash
curl http://localhost:8000/api/v1/dashboard/uptime-report?hours=168
```

---

## API Documentation

Once running, interactive docs are available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Environment Variables

| Variable                   | Default                            | Description                        |
|----------------------------|------------------------------------|------------------------------------|
| `DATABASE_URL`             | `sqlite:///./health_monitor.db`    | Database connection string         |
| `REDIS_URL`                | `redis://localhost:6379/0`         | Redis connection URL               |
| `CELERY_BROKER_URL`        | `redis://localhost:6379/1`         | Celery broker URL                  |
| `SLACK_WEBHOOK_URL`        | —                                  | Default Slack webhook              |
| `DISCORD_WEBHOOK_URL`      | —                                  | Default Discord webhook            |
| `SMTP_HOST`                | —                                  | SMTP server host                   |
| `SMTP_PORT`                | `587`                              | SMTP server port                   |
| `INCIDENT_THRESHOLD`       | `3`                                | Consecutive failures before alert  |
| `RESPONSE_TIME_WARNING_MS` | `2000`                             | Response time degraded threshold   |

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
