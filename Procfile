web: uvicorn sudodev.server.main:app --host 0.0.0.0 --port $PORT
worker: celery -A sudodev.worker.celery_app worker --loglevel=info --concurrency=1
