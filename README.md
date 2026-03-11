# Lab 02 — Architectures of Distributed and Cloud Systems

**Cloud Computing — Bachelor Computer Science, TH Ulm**

## Repository Structure

```
lab02-architectures/
├── docker-compose.yml
├── db/
│   └── init.sql
├── api/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── nginx.conf
│   └── Dockerfile
└── .github/
    └── workflows/
        └── build-push.yml
```

## Quick Start

```bash
git clone https://github.com/eberhardinger-b/cloud-computing-02-architectures.git
cd 2_Architecture
docker compose up -d
```

Open http://localhost:8080 in your browser.

## Stop

```bash
docker compose down        # keeps notes (volume preserved)
docker compose down -v     # removes volume — notes lost
```

## Key Lab Commands

```bash
# Check running containers
docker compose ps

# Scale API to 3 instances
docker compose up -d --scale api=3

# Observe instance distribution (30 requests)
for i in $(seq 1 30); do
  curl -s -I http://localhost:8080/api/notes | awk -F': ' '/X-Instance-ID/ {print $2}'
done | sort | uniq -c

# Simulate DB failure
docker compose stop db

# Restore DB
docker compose start db

# Inspect environment variables on api container
docker compose exec api env | grep -E '^(DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD|APP_VERSION)='

# View API logs
docker compose logs api --tail=30
```

Note: If distribution still appears sticky after scaling, rebuild/restart frontend after nginx changes:

```bash
docker compose up -d --build frontend
```

## API Reference

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET    | `/api/notes` | — | List all notes |
| POST   | `/api/notes` | `{"text": "...", "request_id": "<uuid>"}` | Create note (idempotent) |
| DELETE | `/api/notes/<id>` | — | Delete a note |
| GET    | `/health` | — | Health check + instance ID |

## Design Decisions Mapped to Lab Questions

| Decision | Location | Lab Question |
|----------|----------|--------------|
| Config via env vars | `docker-compose.yml` | Q1.2 |
| Named volume for DB | `docker-compose.yml` | Q1.3 |
| `X-Instance-ID` response header | `api/app.py` | Q2.1, Q2.2 |
| `connect_timeout=5` | `api/app.py` | Q3.1, Q3.2 |
| HTTP 503 on DB failure | `api/app.py` | Q3.2 |
| Idempotency key + `ON CONFLICT DO NOTHING` | `api/app.py` + `db/init.sql` | Q3.3 |
| `crypto.randomUUID()` sent from browser | `frontend/index.html` | Q3.3 |
| nginx reverse proxy with DNS-based upstream resolution | `frontend/nginx.conf` | Q2.1 |

## Pre-built Images

If students cannot build locally:

```bash
# Edit docker-compose.yml: replace `build: ./api` with:
#   image: ghcr.io/th-ulm-cloud/lab02-api:latest
# and `build: ./frontend` with:
#   image: ghcr.io/th-ulm-cloud/lab02-frontend:latest
docker compose up -d
```
