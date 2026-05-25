from fastapi.testclient import TestClient
import api.app as app_module

app = app_module.app


class FakeCollection:
    def __init__(self):
        self.data = []

    def insert_one(self, document):
        self.data.append(document)
        return {"inserted_id": len(self.data)}

    def find_one(self, query, projection=None):
        for item in self.data:
            if item.get("taskId") == query.get("taskId"):
                result = item.copy()
                if projection and projection.get("_id") == 0:
                    result.pop("_id", None)
                return result
        return None

    def find(self, query=None, projection=None):
        results = []
        for item in self.data:
            row = item.copy()
            if projection and projection.get("_id") == 0:
                row.pop("_id", None)
            results.append(row)
        return results

    def update_one(self, query, update):
        for item in self.data:
            if item.get("taskId") == query.get("taskId"):
                if "$set" in update:
                    item.update(update["$set"])

    def clear(self):
        self.data = []


class FakeDB:
    def __init__(self):
        self.collections = {
            "tasks": FakeCollection(),
            "notas": FakeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]

    def command(self, cmd):
        return {"ok": 1}


fake_db = FakeDB()


def fake_get_db():
    return fake_db


class FakeChannel:
    def queue_declare(self, queue, durable=True):
        return None

    def basic_publish(self, exchange, routing_key, body, properties=None):
        return None


class FakeConnection:
    def channel(self):
        return FakeChannel()

    def close(self):
        return None


def fake_blocking_connection(params):
    return FakeConnection()


app_module.get_db = fake_get_db
app_module.pika.BlockingConnection = fake_blocking_connection

client = TestClient(app)


def setup_function():
    fake_db.collections["tasks"].clear()
    fake_db.collections["notas"].clear()


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "API REST de notas activa"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_crear_nota():
    payload = {
        "estudiante": "Ana Lopez",
        "materia": "Matematicas",
        "calificacion": 4.5,
        "fecha": "2026-02-22"
    }

    response = client.post("/notas", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "taskId" in body
    assert body["status"] == "pending"


def test_task_no_encontrada():
    response = client.get("/tasks/no-existe")
    assert response.status_code == 404


def test_listar_notas():
    response = client.get("/notas")
    assert response.status_code == 200
    assert isinstance(response.json(), list)