FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git docker.io curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY sudodev ./sudodev

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn[standard] websockets pydantic

RUN pip install --no-cache-dir swebench

RUN mkdir -p /app/cache/swebench

EXPOSE 8000

# Run the application
CMD ["uvicorn", "sudodev.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
