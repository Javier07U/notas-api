import json
import os
import time
import pika
from pymongo import MongoClient
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


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
# Callback del Worker
# ==========================================

def callback(ch, method, properties, body):
    data = json.loads(body)
    db = get_db()
    notas_collection = db["notas"]
    tasks_collection = db["tasks"]

    task_id = data["taskId"]

    tasks_collection.update_one(
        {"taskId": task_id},
        {"$set": {"status": "running", "updatedAt": datetime.utcnow().isoformat()}},
    )

    try:
        notas_collection.insert_one(
            {
                "taskId": task_id,
                "estudiante": data["estudiante"],
                "materia": data["materia"],
                "calificacion": data["calificacion"],
                "fecha": data["fecha"],
            }
        )

        tasks_collection.update_one(
            {"taskId": task_id},
            {"$set": {"status": "done", "updatedAt": datetime.utcnow().isoformat()}},
        )

    except Exception as exc:
        tasks_collection.update_one(
            {"taskId": task_id},
            {
                "$set": {
                    "status": "error",
                    "error": str(exc),
                    "updatedAt": datetime.utcnow().isoformat(),
                }
            },
        )

    ch.basic_ack(delivery_tag=method.delivery_tag)


# ==========================================
# Loop principal
# ==========================================

while True:
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=5672,
                credentials=pika.PlainCredentials("admin", "password123"),
                heartbeat=600
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
        print("Worker esperando mensajes...")
        channel.start_consuming()
    except Exception as exc:
        print(f"Error conectando al broker: {exc}. Reintentando en 5 segundos...")
        time.sleep(5)
