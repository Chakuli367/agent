# app.py
from flask import Flask, request, jsonify
from goalgrid_agent import GoalGridAgent
from datetime import datetime

app = Flask(__name__)

# ---------- Helper to initialize agent ----------
def get_agent(user_id: str):
    return GoalGridAgent(user_id)

# ---------- Endpoints ----------

@app.route("/create_lesson", methods=["POST"])
def create_lesson():
    data = request.json or {}
    user_id = data.get("user_id")
    context = data.get("context", {})
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    agent = get_agent(user_id)
    lesson = agent.create_daily_lesson(context)
    return jsonify({"message": "Lesson created", "lesson": lesson.__dict__})

@app.route("/generate_tasks", methods=["POST"])
def generate_tasks():
    data = request.json or {}
    user_id = data.get("user_id")
    num_tasks = data.get("num_tasks", 3)
    date = data.get("date")
    if not user_id or not date:
        return jsonify({"error": "user_id and date are required"}), 400

    agent = get_agent(user_id)
    lesson_data = agent.get_lesson(date)
    if not lesson_data:
        return jsonify({"error": "Lesson not found"}), 404

    # Reconstruct Lesson object from saved data
    lesson = agent.create_daily_lesson()  # placeholder to get Lesson type
    lesson.__dict__.update(lesson_data)
    tasks = agent.generate_tasks_for_lesson(lesson, num_tasks)
    return jsonify({"message": "Tasks generated", "tasks": [t.to_dict() for t in tasks]})

@app.route("/regenerate_tasks", methods=["POST"])
def regenerate_tasks():
    data = request.json or {}
    user_id = data.get("user_id")
    date = data.get("date")
    instructions = data.get("instructions", "Simplify these tasks for a beginner")
    if not user_id or not date:
        return jsonify({"error": "user_id and date are required"}), 400

    agent = get_agent(user_id)
    success = agent.regenerate_tasks_with_ai(date, instructions)
    return jsonify({"success": success})

@app.route("/todays_tasks", methods=["GET"])
def todays_tasks():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    agent = get_agent(user_id)
    tasks = agent.get_todays_tasks()
    return jsonify({"tasks": tasks})

@app.route("/summarize_lesson", methods=["GET"])
def summarize_lesson():
    user_id = request.args.get("user_id")
    date = request.args.get("date", datetime.now().date().isoformat())
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    agent = get_agent(user_id)
    summary = agent.summarize_todays_lesson() if date == datetime.now().date().isoformat() else None
    return jsonify({"summary": summary})

@app.route("/all_users", methods=["GET"])
def all_users():
    agent = get_agent("dummy")  # Just to access the class method
    users = agent.get_all_users()
    return jsonify(users)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
