FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

VOLUME ["/data", "/config"]

ENTRYPOINT ["python", "-m", "fritzlog", "/config/config.yaml"]
