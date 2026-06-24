FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MM_ENV=production

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Set MM_SECRET_KEY and MM_DATABASE_URL at runtime, e.g.:
# docker run -e MM_SECRET_KEY=... -e MM_DATABASE_URL=... -p 8000:8000 money-mirror
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
