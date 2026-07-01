import os
import uuid
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify, g
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

# Import signals
from signal_groq import analyze_text as analyze_text_groq
from signal_stylometrics import analyze_stylometrics

app = Flask(__name__)

# Setup Flask-Limiter (Milestone 5)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day"],
    storage_uri="memory://"
)

DATABASE = 'audit_log.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create table with all required fields
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                creator_id TEXT,
                timestamp TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                llm_score REAL,
                stylometric_score REAL,
                status TEXT NOT NULL,
                appeal_reasoning TEXT
            )
        ''')
        db.commit()

# Initialize DB on startup
init_db()

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute")
def submit():
    data = request.json
    if not data or 'text' not in data or 'creator_id' not in data:
        return jsonify({"error": "Missing 'text' or 'creator_id' in request body"}), 400
    
    text = data['text']
    creator_id = data['creator_id']
    content_id = str(uuid.uuid4())
    
    # Milestone 3 & 4: Get signals and calculate combined confidence
    groq_result = analyze_text_groq(text)
    stylo_result = analyze_stylometrics(text)
    
    llm_score = groq_result.get("llm_score", 0.5)
    stylo_score = stylo_result.get("stylometric_score", 0.5)
    
    # Combine the signals (simple average)
    confidence = (llm_score + stylo_score) / 2.0
    
    # Milestone 5: Transparency Labels based on thresholds
    if confidence >= 0.66:
        attribution = "likely_ai"
        label = "Likely AI-Generated: Our analysis indicates structural and stylistic patterns strongly associated with artificial intelligence models."
    elif confidence <= 0.35:
        attribution = "likely_human"
        label = "Verified Original: This work exhibits the stylistic variance and natural patterns characteristic of human creativity."
    else:
        attribution = "uncertain"
        label = "Attribution Unclear: This content contains a mix of signals. It may be heavily edited human work, or AI-assisted."
        
    status = "classified"
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Log to SQLite
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO logs (content_id, creator_id, timestamp, attribution, confidence, llm_score, stylometric_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (content_id, creator_id, timestamp, attribution, confidence, llm_score, stylo_score, status))
    db.commit()
    
    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": round(confidence, 3),
        "label": label,
        "llm_score": llm_score,
        "stylometric_score": stylo_score,
        "llm_reasoning": groq_result.get("llm_reasoning"),
        "stylometric_metrics": stylo_result.get("metrics")
    }), 200


@app.route("/appeal", methods=["POST"])
@limiter.limit("5 per minute")
def appeal():
    """Milestone 5: Appeals Workflow"""
    data = request.json
    if not data or 'content_id' not in data or 'creator_reasoning' not in data:
        return jsonify({"error": "Missing 'content_id' or 'creator_reasoning' in request body"}), 400
        
    content_id = data['content_id']
    reasoning = data['creator_reasoning']
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if the content exists
    cursor.execute('SELECT id FROM logs WHERE content_id = ?', (content_id,))
    if not cursor.fetchone():
        return jsonify({"error": "content_id not found"}), 404
        
    # Update status and reasoning
    cursor.execute('''
        UPDATE logs
        SET status = 'under_review', appeal_reasoning = ?
        WHERE content_id = ?
    ''', (reasoning, content_id))
    db.commit()
    
    return jsonify({
        "message": "Appeal received successfully. Status updated to under_review.",
        "content_id": content_id
    }), 200


@app.route("/log", methods=["GET"])
def get_logs():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM logs ORDER BY id DESC LIMIT 50')
    rows = cursor.fetchall()
    
    entries = []
    for row in rows:
        entries.append({
            "id": row["id"],
            "content_id": row["content_id"],
            "creator_id": row["creator_id"],
            "timestamp": row["timestamp"],
            "attribution": row["attribution"],
            "confidence": row["confidence"],
            "llm_score": row["llm_score"],
            "stylometric_score": row["stylometric_score"],
            "status": row["status"],
            "appeal_reasoning": row["appeal_reasoning"]
        })
        
    return jsonify({"entries": entries}), 200

if __name__ == "__main__":
    # Note: Using port 5001 instead of default 5000 to avoid conflict with macOS AirPlay Receiver
    app.run(host="0.0.0.0", port=5001, debug=True)
