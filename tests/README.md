# Tests

## Backend Tests

```bash
cd backend

# Run all tests
pytest -xvs

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_time.py -xvs
```

## Frontend Tests

```bash
cd frontend

# Run all tests
npm run test

# Run with coverage
npm run test:ci

# Run specific test file
npm run test -- tests/components.test.tsx
```