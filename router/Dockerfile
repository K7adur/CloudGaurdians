
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip --default-timeout=300 install --retries=10 --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]