from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
import pika
import uuid
import json
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

app = FastAPI(title="Notas API")


# ==========================================
# Parameter Store
# ==========================================

def get_ssm_parameter(name: str, default: str = None) -> str:
    """
    Consulta un parámetro del Parameter Store de AWS.
    Si no existe, retorna el valor `default`.
    """
    client = boto3.client("ssm", region_name="us-east-1")
    try:
        response = client.get_parameter(Name=name)
        return response["Parameter"]["Value"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            print(f"[WARN] Parámetro '{name}' no encontrado. Usando valor por defecto: '{default}'")
            return default
        raise


# ==========================================
# Configuración — IPs desde Parameter Store
# ==========================================

_mongo_ip = get_ssm_parameter(
    name="/notas-api/dev/mongodb/public_ip",
    default=os.getenv("MONGO_HOST", "localhost"),
)

_rabbitmq_ip = get_ssm_parameter(
    name="/notas-api/dev/rabbitmq/public_ip",
    default=os.getenv("RABBITMQ_HOST", "localhost"),
)

MONGO_URI = f"mongodb://{_mongo_ip}:27017/"
RABBITMQ_HOST = _rabbitmq_ip
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "notas_queue")
DB_NAME = os.getenv("MONGO_DB", "notasdb")

print(f"[INFO] MongoDB URI: {MONGO_URI}")
print(f"[INFO] RabbitMQ Host: {RABBITMQ_HOST}")


# ==========================================
# DB helper
# ==========================================

def get_db():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db


# ==========================================
# Modelos
# ==========================================

class Nota(BaseModel):
    estudiante: str = Field(..., min_length=2, max_length=100)
    materia: str = Field(..., min_length=2, max_length=100)
    calificacion: float = Field(..., ge=0, le=5)
    fecha: str | None = None


# ==========================================
# Endpoints
# ==========================================

@app.get("/")
def root():
    return {"message": "API REST de notas activa"}


@app.get("/health")
def health():
    try:
        db = get_db()
        db.command("ping")
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Servicio no disponible: {exc}")


@app.post("/notas")
def crear_nota(nota: Nota):
    task_id = str(uuid.uuid4())
    db = get_db()
    tasks_collection = db["tasks"]

    task_document = {
        "taskId": task_id,
        "operation": "guardar_calificacion",
        "status": "pending",
        "createdAt": datetime.utcnow().isoformat(),
    }
    tasks_collection.insert_one(task_document)

    mensaje = {
        "taskId": task_id,
        "operation": "guardar_calificacion",
        "estudiante": nota.estudiante,
        "materia": nota.materia,
        "calificacion": nota.calificacion,
        "fecha": nota.fecha or datetime.utcnow().date().isoformat(),
    }

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
        )
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
    except Exception as exc:
        tasks_collection.update_one(
            {"taskId": task_id},
            {"$set": {"status": "error", "error": str(exc)}},
        )
        raise HTTPException(status_code=503, detail=f"No se pudo enviar la tarea: {exc}")

    return {
        "message": "Nota enviada para procesamiento asíncrono",
        "taskId": task_id,
        "status": "pending",
    }


@app.get("/tasks/{task_id}")
def obtener_estado(task_id: str):
    db = get_db()
    tasks_collection = db["tasks"]
    task = tasks_collection.find_one({"taskId": task_id}, {"_id": 0})

    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    return task


@app.get("/notas")
def listar_notas():
    db = get_db()
    notas_collection = db["notas"]
    notas = list(notas_collection.find({}, {"_id": 0}))
    return notas
