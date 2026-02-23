import os
import socket
import uuid

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request

app = Flask(__name__)

def get_db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )

@app.after_request
def add_instance_header(response):
    response.headers["X-Instance-ID"] = socket.gethostname()
    response.headers["X-App-Version"] = os.environ.get("APP_VERSION", "unknown")
    return response

@app.route("/health")
def health():
    return jsonify({"status": "ok", "instance": socket.gethostname()})

@app.route("/api/notes", methods=["GET"])
def list_notes():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, text, created_at FROM notes ORDER BY created_at DESC")
        notes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([dict(n) for n in notes])
    except psycopg2.OperationalError as e:
        return jsonify({"error": "Database unavailable", "detail": str(e)}), 503

@app.route("/api/notes", methods=["POST"])
def create_note():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Field 'text' is required"}), 400

    request_id = data.get("request_id") or str(uuid.uuid4())

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO notes (text, request_id)
            VALUES (%s, %s)
            ON CONFLICT (request_id) DO NOTHING
            RETURNING id, text, created_at
            """,
            (text, request_id),
        )
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if result:
            return jsonify(dict(result)), 201
        return jsonify({"message": "Duplicate request, note already saved"}), 200
    except psycopg2.OperationalError as e:
        return jsonify({"error": "Database unavailable", "detail": str(e)}), 503

@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notes WHERE id = %s RETURNING id", (note_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            return jsonify({"deleted": note_id}), 200
        return jsonify({"error": "Note not found"}), 404
    except psycopg2.OperationalError as e:
        return jsonify({"error": "Database unavailable", "detail": str(e)}), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
