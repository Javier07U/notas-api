import json
import os
import time
import pika
from pymongo import MongoClient
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "notas_queue")
DB_NAME = os.getenv("MONGO_DB", "notasdb")


def get_db():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db


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


while True:
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
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