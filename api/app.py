from datetime import date, datetime
import json
import os
import uuid

import pika
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import MongoClient

app = FastAPI(title="Notas API", version="2.0.0")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "notas_queue")
DB_NAME = os.getenv("MONGO_DB", "notasdb")

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = mongo_client[DB_NAME]


def get_db():
    return db


def get_rabbit_connection():
    if RABBITMQ_URL:
        return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
    )


class NotaCreate(BaseModel):
    estudiante: str = Field(..., min_length=2, max_length=100)
    materia: str = Field(..., min_length=2, max_length=100)
    calificacion: float = Field(..., ge=0, le=5)
    fecha: date | None = None


class NotaUpdate(BaseModel):
    estudiante: str | None = Field(default=None, min_length=2, max_length=100)
    materia: str | None = Field(default=None, min_length=2, max_length=100)
    calificacion: float | None = Field(default=None, ge=0, le=5)
    fecha: date | None = None


@app.get("/")
def root():
    return {"message": "API REST de notas activa", "version": "2.0.0"}


@app.get("/health")
def health():
    try:
        get_db().command("ping")
        connection = get_rabbit_connection()
        connection.close()
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Servicio no disponible: {exc}")


def create_task(operation: str, payload: dict):
    task_id = str(uuid.uuid4())
    task_document = {
        "taskId": task_id,
        "operation": operation,
        "status": "pending",
        "createdAt": datetime.utcnow().isoformat(),
    }
    get_db()["tasks"].insert_one(task_document)

    message = {"taskId": task_id, "operation": operation, **payload}

    try:
        connection = get_rabbit_connection()
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(message, default=str),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
    except Exception as exc:
        get_db()["tasks"].update_one(
            {"taskId": task_id},
            {"$set": {"status": "error", "error": str(exc)}},
        )
        raise HTTPException(status_code=503, detail=f"No se pudo enviar la tarea: {exc}")

    return {
        "message": "Tarea enviada para procesamiento asíncrono",
        "taskId": task_id,
        "operation": operation,
        "status": "pending",
    }


@app.post("/notas", status_code=202)
def crear_nota(nota: NotaCreate):
    return create_task(
        "crear_nota",
        {
            "estudiante": nota.estudiante,
            "materia": nota.materia,
            "calificacion": nota.calificacion,
            "fecha": (nota.fecha or datetime.utcnow().date()).isoformat(),
        },
    )


@app.put("/notas/{nota_id}", status_code=202)
def actualizar_nota(nota_id: str, nota: NotaUpdate):
    changes = nota.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    if "fecha" in changes and changes["fecha"] is not None:
        changes["fecha"] = changes["fecha"].isoformat()
    return create_task("actualizar_nota", {"notaId": nota_id, "changes": changes})


@app.delete("/notas/{nota_id}", status_code=202)
def borrar_nota(nota_id: str):
    return create_task("borrar_nota", {"notaId": nota_id})


@app.get("/tasks/{task_id}")
def obtener_estado(task_id: str):
    task = get_db()["tasks"].find_one({"taskId": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    return task


@app.get("/notas")
def listar_notas(
    estudiante: str | None = Query(default=None),
    materia: str | None = Query(default=None),
):
    query = {}
    if estudiante:
        query["estudiante"] = estudiante
    if materia:
        query["materia"] = materia
    return list(get_db()["notas"].find(query, {"_id": 0}))


@app.get("/notas/{nota_id}")
def consultar_nota(nota_id: str):
    nota = get_db()["notas"].find_one({"notaId": nota_id}, {"_id": 0})
    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return nota
