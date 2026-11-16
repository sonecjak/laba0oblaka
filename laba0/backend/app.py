import os
import socket
import time
from contextlib import contextmanager

import psycopg2
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="../frontend", static_url_path="")

# Всё, что меняется между окружениями, берём из переменных окружения.
# Значения по умолчанию подходят для локального запуска из README.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "lab0"),
    "user": os.environ.get("DB_USER", "lab0"),
    "password": os.environ.get("DB_PASSWORD", "lab0"),
    "connect_timeout": 3,
}
# Идентификатор экземпляра бэкенда: по нему в Лабе 1 видно, какая копия ответила.
INSTANCE_ID = os.environ.get("INSTANCE_ID", socket.gethostname())
MAX_TEXT_LEN = 1000


@contextmanager
def db_cursor():
    """Новое соединение на каждый запрос.

    Если БД перезапустилась (Лаба 2, звёздочка), следующий запрос просто
    подключится заново, а не упадёт на протухшем соединении.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn:  # commit при успехе, rollback при ошибке
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def init_db(retries=30, delay=2):
    """Создаёт таблицу. Если БД ещё поднимается, ждёт, а не падает сразу."""
    for attempt in range(1, retries + 1):
        try:
            with db_cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, text TEXT)"
                )
            return
        except psycopg2.OperationalError as e:
            print(f"БД недоступна (попытка {attempt}/{retries}): {str(e).strip()}", flush=True)
            time.sleep(delay)
    raise RuntimeError("не удалось подключиться к БД")


@app.after_request
def add_instance_header(response):
    response.headers["X-Backend-Id"] = INSTANCE_ID
    return response


@app.errorhandler(psycopg2.OperationalError)
def handle_db_unavailable(e):
    app.logger.error("БД недоступна: %s", e)
    return jsonify({"error": "database unavailable"}), 503


@app.errorhandler(psycopg2.Error)
def handle_db_error(e):
    app.logger.error("Ошибка БД: %s", e)
    return jsonify({"error": "database error"}), 500


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    with db_cursor() as cur:
        cur.execute("SELECT 1")
    return jsonify({"status": "ok", "backend": INSTANCE_ID})


@app.route("/api/notes", methods=["GET"])
def get_notes():
    with db_cursor() as cur:
        cur.execute("SELECT id, text FROM notes ORDER BY id DESC")
        rows = cur.fetchall()
    return jsonify([{"id": i, "text": t} for i, t in rows])


@app.route("/api/notes", methods=["POST"])
def add_note():
    data = request.get_json(silent=True)
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text is required"}), 400
    text = text.strip()
    if len(text) > MAX_TEXT_LEN:
        return jsonify({"error": f"text is too long (max {MAX_TEXT_LEN})"}), 400
    with db_cursor() as cur:
        cur.execute("INSERT INTO notes (text) VALUES (%s)", (text,))
    return jsonify({"status": "ok"}), 201


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
