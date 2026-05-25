# API REST de Notas de Estudiantes

Proyecto académico que implementa una API REST para registrar y consultar notas de estudiantes.

## Descripción

El sistema permite:

- Consultar notas de forma síncrona
- Registrar notas de forma asíncrona
- Consultar el estado de una tarea mediante `taskId`

## Arquitectura

Componentes principales:

- **FastAPI**: expone los endpoints REST
- **RabbitMQ**: cola de mensajes para procesamiento asíncrono
- **Worker**: procesa mensajes y guarda datos
- **MongoDB**: almacena notas y tareas
- **Docker Compose**: orquesta todos los servicios

## Endpoints

### GET `/`
Verifica que la API está activa.

### GET `/health`
Verifica la salud de la API y conexión básica.

### POST `/notas`
Registra una nota de forma asíncrona.

Ejemplo body:

```json
{
  "estudiante": "Ana Lopez",
  "materia": "Matematicas",
  "calificacion": 4.5,
  "fecha": "2026-02-22"
}

Respuesta esperada:

{
  "message": "Nota enviada para procesamiento asíncrono",
  "taskId": "uuid",
  "status": "pending"
}
GET /tasks/{task_id}

Consulta el estado de una tarea.

GET /notas

Lista las notas guardadas.

Swagger

Disponible en:

http://localhost:8000/docs
Ejecución con Docker
Requisitos

Docker

Docker Compose

Comando de ejecución
docker compose up --build
Pruebas unitarias

Instalar dependencias:

pip install -r api/requirements.txt

Ejecutar pruebas:

python -m pytest
Chequeo de código estático
flake8 api worker tests
Despliegue en EC2

Crear una instancia EC2 Ubuntu

Instalar Docker y Docker Compose

Clonar el repositorio

Ejecutar:

docker compose up --build -d

Abrir el puerto 8000 en el Security Group

Probar en:

http://IP_PUBLICA:8000/docs
Dependencias PyPI

Este proyecto usa paquetes instalados con pip desde PyPI:

fastapi

uvicorn

pika

pymongo

pytest

httpx

flake8