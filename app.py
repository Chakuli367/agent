# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from goalgrid_agent import GoalGridAgent, Lesson
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests (needed for Render frontend)

# ---------- Helper to initialize agent ----------
def get_agent(user_id: str):
    return GoalGridAgent(user_id)

# ---------- Endpoints ----------

@app.route("/create_lesson", methods=["POST"])
def create_lesson():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    context = data.get("context", {})
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    agent = get_agent(user_id)
    lesson = agent.create_daily_lesson(context)
    return jsonify({"message": "Lesson created", "lesson": lesson.__dict__})

@app.route("/generate_tasks", methods=["POST"])
def generate_tasks():
    data = request.get_json(force=True)
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
    lesson = Lesson(
        date=date,
        title=lesson_data["title"],
        lesson=lesson_data["lesson"],
        summary=lesson_data["summary"],
        motivation=lesson_data["motivation"],
        quote=lesson_data["quote"],
        secret_hacks_and_shortcuts=lesson_data["secret_hacks_and_shortcuts"],
        tiny_daily_rituals_that_transform=lesson_data["tiny_daily_rituals_that_transform"],
        visual_infographic_html=lesson_data["visual_infographic_html"],
        tasks=[Task(t["title"], t["task"]["task"]) for t in lesson_data.get("tasks", [])]
    )

    tasks = agent.generate_tasks_for_lesson(lesson, num_tasks)
    return jsonify({"message": "Tasks generated", "tasks": [t.to_dict() for t in tasks]})
@app.route("/regenerate_tasks", methods=["POST"])
def regenerate_tasks():
    data = request.get_json(force=True)
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
    if date == datetime.now().date().isoformat():
        summary = agent.summarize_todays_lesson()
    else:
        lesson_data = agent.get_lesson(date)
        summary = lesson_data.get("summary") if lesson_data else None
    return jsonify({"summary": summary})

@app.route("/all_users", methods=["GET"])
def all_users():
    agent = get_agent("dummy")  # Just to access the class method
    agent.get_all_users()  # Prints to console
    return jsonify({"message": "Check console for all users"})

# ---------- Health check ----------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ---------- Main ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
