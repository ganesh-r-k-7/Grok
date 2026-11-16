# GROK

Personal AI Command Center - a dashboard that aggregates your calendar, email, and tasks with an AI assistant.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system design.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### Development

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend

# Run backend tests
docker compose exec backend pytest -xvs

# Run frontend tests
docker compose exec frontend npm run test:ci

# Stop all services
docker compose down
```

### Services

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Readiness Check | http://localhost:8000/ready |

## Project Structure

```
grok/
├── frontend/          # Next.js 14 + TypeScript + Tailwind
├── backend/           # FastAPI + SQLAlchemy + PostgreSQL
├── infrastructure/    # Infrastructure configs (future)
├── docs/              # Documentation
├── tests/             # Shared test utilities
├── .github/           # GitHub Actions CI/CD
├── docker-compose.yml # Local development stack
└── ARCHITECTURE.md    # System architecture
```

## Technology Stack

### Frontend
- Next.js 14 (App Router)
- TypeScript (strict mode)
- Tailwind CSS
- TanStack Query (React Query)
- Zustand
- Radix UI
- React Hook Form + Zod

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async)
- Alembic (migrations)
- Pydantic v2
- Redis (Celery broker)
- Celery + APScheduler (background jobs)
- structlog (JSON logging)
- pytest (testing)

### Infrastructure
- PostgreSQL 15
- Redis 7

## Development Commands

```bash
# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest -xvs

# Frontend
cd frontend
npm install
npm run dev
npm run lint
npm run typecheck
npm run test:ci
```


## License

Private project.
