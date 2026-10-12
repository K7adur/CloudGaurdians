
from flask import Flask, jsonify, request
import os
import psycopg2

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "region1-db"),
        database=os.getenv("DB_NAME", "cloudguardians"),
        user=os.getenv("DB_USER", "clouduser"),
        password=os.getenv("DB_PASSWORD", "cloudpass")
    )

@app.route("/")
def home():
    return "PRIMARY REGION - Application is running"

@app.route("/health")
def health():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify(status="healthy", region="primary"), 200
    except Exception as e:
        return jsonify(status="unhealthy", error=str(e)), 503

@app.route("/data")
def get_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, message, created_at FROM disaster_records ORDER BY id"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([
            {
                "id": row[0],
                "message": row[1],
                "created_at": row[2].isoformat() if row[2] else None
            }
            for row in rows
        ])
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/write", methods=["POST"])
def write_data():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")

    if not message or not message.strip():
        return jsonify(error="A non-empty message is required"), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO disaster_records (message) VALUES (%s) RETURNING id, message, created_at",
            (message.strip(),)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()

        return jsonify({
            "status": "saved",
            "id": row[0],
            "message": row[1],
            "created_at": row[2].isoformat() if row[2] else None
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify(error=str(e)), 500
    finally:
        if conn:
            conn.close()

@app.route("/replicate", methods=["POST"])
def replicate_data():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")

    if not message or not message.strip():
        return jsonify(error="A non-empty message is required"), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO disaster_records (message) VALUES (%s) RETURNING id",
            (message.strip(),)
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return jsonify(status="replicated", id=new_id), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify(error=str(e)), 500
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
