FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

COPY pyproject.toml ./
COPY src ./src
COPY specs ./specs
RUN pip install --no-cache-dir -e .

EXPOSE 8080
CMD ["uvicorn", "evoswarm.api:app", "--host", "0.0.0.0", "--port", "8080"]
