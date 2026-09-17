import os
import psycopg2
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="../frontend", static_url_path="")

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname="lab0", user="lab0", password="lab0"
)
conn.autocommit = True
conn.cursor().execute("CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, text TEXT)")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/notes", methods=["GET"])
def get_notes():
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM notes ORDER BY id DESC")
    return jsonify([{"id": i, "text": t} for i, t in cur.fetchall()])


@app.route("/api/notes", methods=["POST"])
def add_note():
    text = request.get_json().get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    conn.cursor().execute("INSERT INTO notes (text) VALUES (%s)", (text,))
    return jsonify({"status": "ok"}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
