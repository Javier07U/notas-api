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
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
    )


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
            document = {
                "notaId": nota_id,
                "taskId": task_id,
                "estudiante": data["estudiante"],
                "materia": data["materia"],
                "calificacion": data["calificacion"],
                "fecha": data["fecha"],
                "createdAt": now,
                "updatedAt": now,
            }
            notas.insert_one(document)
            set_task(task_id, "done", result={"notaId": nota_id})

        elif operation == "actualizar_nota":
            result = notas.update_one(
                {"notaId": data["notaId"]},
                {"$set": {**data["changes"], "updatedAt": now}},
            )
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
