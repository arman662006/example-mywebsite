from flask import Flask, send_from_directory, request, jsonify, session
from textblob import TextBlob
import sqlite3

app = Flask(__name__, static_folder="frontend")
app.secret_key = "change-this-to-a-private-random-key"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"

DATABASE = "feedback.db"


def init_db():
    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            polarity REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return send_from_directory("frontend", "index.html")


@app.route("/admin-dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return send_from_directory("frontend", "login.html")

    return send_from_directory("frontend", "dashboard.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    if filename == "dashboard.html" and not session.get("admin_logged_in"):
        return send_from_directory("frontend", "login.html")

    return send_from_directory("frontend", filename)


@app.route("/analyze", methods=["POST"])
def analyze_feedback():
    data = request.get_json(silent=True) or {}

    student_name = str(data.get("student_name", "")).strip()
    subject = str(data.get("subject", "")).strip()
    feedback = str(data.get("feedback", "")).strip()

    if not student_name or not subject or not feedback:
        return jsonify({"error": "Please fill in all fields."}), 400

    polarity = TextBlob(feedback).sentiment.polarity
    normalized_feedback = " ".join(feedback.lower().split())

    neutral_phrases = [
        "the class was okay",
        "class was okay",
        "the class is okay",
        "class is okay",
        "the class was ok",
        "class was ok",
        "it was okay",
        "it is okay",
        "it was ok",
        "the lecture was okay",
        "the lecture was ok",
        "average class",
        "it was average",
        "nothing special"
    ]

    if any(phrase in normalized_feedback for phrase in neutral_phrases):
        sentiment = "Neutral"
    elif polarity > 0.2:
        sentiment = "Positive"
    elif polarity < -0.2:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        INSERT INTO feedback
        (student_name, subject, feedback_text, sentiment, polarity)
        VALUES (?, ?, ?, ?, ?)
    """, (student_name, subject, feedback, sentiment, polarity))

    conn.commit()
    conn.close()

    return jsonify({
        "student_name": student_name,
        "subject": subject,
        "sentiment": sentiment,
        "polarity": polarity,
        "message": "Feedback analyzed and saved successfully."
    })


@app.route("/dashboard-data")
def dashboard_data():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Please login first."}), 401

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    total = conn.execute(
        "SELECT COUNT(*) FROM feedback"
    ).fetchone()[0]

    rows = conn.execute("""
        SELECT sentiment, COUNT(*) AS count
        FROM feedback
        GROUP BY sentiment
    """).fetchall()

    conn.close()

    counts = {
        "Positive": 0,
        "Negative": 0,
        "Neutral": 0
    }

    for row in rows:
        counts[row["sentiment"]] = row["count"]

    return jsonify({
        "total": total,
        "positive": counts["Positive"],
        "negative": counts["Negative"],
        "neutral": counts["Neutral"]
    })


@app.route("/feedback-list")
def feedback_list():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Please login first."}), 401

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT id, student_name, subject, feedback_text,
               sentiment, created_at
        FROM feedback
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    feedbacks = [dict(row) for row in rows]

    return jsonify(feedbacks)

@app.route("/sentiment-trend")
def sentiment_trend():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Please login first."}), 401

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT DATE(created_at) AS date,
               sentiment,
               COUNT(*) AS count
        FROM feedback
        GROUP BY DATE(created_at), sentiment
        ORDER BY DATE(created_at)
    """).fetchall()

    conn.close()

    trend = {}

    for row in rows:
        date = row["date"]

        if date not in trend:
            trend[date] = {
                "Positive": 0,
                "Negative": 0,
                "Neutral": 0
            }

        trend[date][row["sentiment"]] = row["count"]

    return jsonify(trend)
@app.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True

        return jsonify({
            "message": "Login successful"
        })

    return jsonify({
        "error": "Invalid username or password."
    }), 401


@app.route("/logout")
def admin_logout():
    session.clear()

    return jsonify({
        "message": "Logged out successfully."
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True)