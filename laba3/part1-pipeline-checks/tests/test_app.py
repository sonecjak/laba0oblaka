import pytest

import app as app_module


def add(client, text):
    return client.post("/api/notes", json={"text": text})


# --- служебные маршруты ---------------------------------------------------


def test_index_serves_frontend(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Заметки" in resp.get_data(as_text=True)


def test_health_checks_database(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "backend": app_module.INSTANCE_ID}


def test_every_response_has_backend_id_header(client):
    assert client.get("/api/notes").headers["X-Backend-Id"] == app_module.INSTANCE_ID


# --- заметки ---------------------------------------------------------------


def test_notes_empty_at_start(client):
    resp = client.get("/api/notes")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_add_note_is_saved_to_db(client):
    resp = add(client, "купить молоко")
    assert resp.status_code == 201
    assert resp.get_json() == {"status": "ok"}
    assert client.get("/api/notes").get_json() == [{"id": 1, "text": "купить молоко"}]


def test_text_is_stripped(client):
    add(client, "   с пробелами   ")
    assert client.get("/api/notes").get_json()[0]["text"] == "с пробелами"


def test_newest_note_comes_first(client):
    add(client, "первая")
    add(client, "вторая")
    texts = [n["text"] for n in client.get("/api/notes").get_json()]
    assert texts == ["вторая", "первая"]


def test_max_length_text_is_accepted(client):
    resp = add(client, "я" * app_module.MAX_TEXT_LEN)
    assert resp.status_code == 201


# --- валидация -------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "    "},
        {"text": 123},
        {"text": None},
        {},
        ["не", "объект"],
    ],
    ids=["empty", "spaces", "number", "null", "no-text", "list"],
)
def test_invalid_json_is_rejected(client, payload):
    resp = client.post("/api/notes", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "text is required"}
    assert client.get("/api/notes").get_json() == []


def test_not_json_body_is_rejected(client):
    resp = client.post("/api/notes", data="просто текст", content_type="text/plain")
    assert resp.status_code == 400


def test_too_long_text_is_rejected(client):
    resp = add(client, "я" * (app_module.MAX_TEXT_LEN + 1))
    assert resp.status_code == 400
    assert "too long" in resp.get_json()["error"]
    assert client.get("/api/notes").get_json() == []


# --- недоступная база ------------------------------------------------------


def test_database_down_returns_503(client, monkeypatch):
    # Порт 1 заведомо закрыт: подключение к БД падает с OperationalError.
    monkeypatch.setitem(app_module.DB_CONFIG, "port", "1")
    resp = client.get("/api/notes")
    assert resp.status_code == 503
    assert resp.get_json() == {"error": "database unavailable"}
