#!/bin/bash
set -euxo pipefail
exec > /var/log/notas-backend-user-data.log 2>&1

dnf update -y
dnf install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user || true

mkdir -p /opt/notas-backend/worker
cd /opt/notas-backend

cat > docker-compose.yml <<'EOF'
services:
  mongo:
    image: mongo:7
    container_name: notas_mongo
    restart: unless-stopped
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: password123
    volumes:
      - mongo_data:/data/db

  rabbitmq:
    image: rabbitmq:3-management
    container_name: notas_rabbitmq
    restart: unless-stopped
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: password123
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  worker:
    build: ./worker
    container_name: notas_worker
    restart: unless-stopped
    environment:
      MONGO_URI: mongodb://admin:password123@mongo:27017/?authSource=admin
      MONGO_DB: notasdb
      RABBITMQ_URL: amqp://admin:password123@rabbitmq:5672/
      RABBITMQ_QUEUE: notas_queue
    depends_on:
      - mongo
      - rabbitmq

volumes:
  mongo_data:
EOF

cat > worker/Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /worker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker.py .
CMD ["python", "worker.py"]
EOF

cat > worker/requirements.txt <<'EOF'
pika
pymongo
EOF

cat > worker/worker.py <<'PY'
from datetime import datetime
import json
import os
import time
import uuid
import pika
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "notas_queue")
DB_NAME = os.getenv("MONGO_DB", "notasdb")

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = mongo_client[DB_NAME]

def get_rabbit_connection():
    if RABBITMQ_URL:
        return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600))

def set_task(task_id, status, **extra):
    payload = {"status": status, "updatedAt": datetime.utcnow().isoformat(), **extra}
    db["tasks"].update_one({"taskId": task_id}, {"$set": payload})

def callback(ch, method, properties, body):
    data = json.loads(body)
    task_id = data["taskId"]
    operation = data["operation"]
    set_task(task_id, "running")
    try:
        notas = db["notas"]
        now = datetime.utcnow().isoformat()
        if operation == "crear_nota":
            nota_id = str(uuid.uuid4())
            document = {"notaId": nota_id, "taskId": task_id, "estudiante": data["estudiante"], "materia": data["materia"], "calificacion": data["calificacion"], "fecha": data["fecha"], "createdAt": now, "updatedAt": now}
            notas.insert_one(document)
            set_task(task_id, "done", result={"notaId": nota_id})
        elif operation == "actualizar_nota":
            result = notas.update_one({"notaId": data["notaId"]}, {"$set": {**data["changes"], "updatedAt": now}})
            if result.matched_count == 0:
                raise ValueError("Nota no encontrada")
            set_task(task_id, "done", result={"notaId": data["notaId"]})
        elif operation == "borrar_nota":
            result = notas.delete_one({"notaId": data["notaId"]})
            if result.deleted_count == 0:
                raise ValueError("Nota no encontrada")
            set_task(task_id, "done", result={"notaId": data["notaId"]})
        else:
            raise ValueError(f"Operación no soportada: {operation}")
    except Exception as exc:
        set_task(task_id, "error", error=str(exc))
    ch.basic_ack(delivery_tag=method.delivery_tag)

while True:
    try:
        connection = get_rabbit_connection()
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
        print("Worker esperando mensajes...")
        channel.start_consuming()
    except Exception as exc:
        print(f"Error conectando al broker: {exc}. Reintentando en 5 segundos...")
        time.sleep(5)
PY

docker compose up -d --build
