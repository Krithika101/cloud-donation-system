# Cloud deployment guide

This project is prepared for a Linux-hosted deployment using Gunicorn.

## Prerequisites

- A GitHub repository containing this project
- A Render account or another Linux-compatible host
- A PostgreSQL database instance

## Required environment variables

Set these in the hosting platform dashboard:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: any long random secret value
- `FLASK_ENV=production`

## Render deployment

1. Push this repository to GitHub.
2. In Render, create a new Web Service.
3. Connect the GitHub repository.
4. Use the following values:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
5. Add the environment variables above.
6. Deploy the service.

## Docker deployment

This repository also includes a Dockerfile for container-based deployment.

Build locally:

```bash
docker build -t cloud-donation-system .
docker run -p 5000:5000 -e DATABASE_URL="postgresql://..." -e SECRET_KEY="your-secret" cloud-donation-system
```

## Notes

- Gunicorn is a Linux/Unix runtime and should not be used as a production server on Windows.
- This is why the app is configured for Render or another Linux host.
- The app was validated locally with tests: `pytest -q` -> 6 passed.
