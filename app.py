from flask import Flask, request, jsonify, abort
from goalgrid_agent import GoalGridAgent, Lesson, Task
from datetime import datetime

app = Flask(__name__)

# ===== REQUEST HELPERS =====
def parse_context(data):
    return data.get("recent_progress", None)

def parse_difficulty(data):
    return data.get("difficulty_instructions", "Make these tasks simpler and easier to complete for a beginner")

# ===== ENDPOINTS =====

@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "GoalGrid Backend is running!"})

# ---------- User Helpers ----------
@app.route("/user/<user_id>", methods=["GET"])
def get_user(user_id):
    agent = GoalGridAgent(user_id)
    return jsonify(agent.get_user_data())

@app.route("/users", methods=["GET"])
def get_all_users():
    agent = GoalGridAgent("dummy")  # user_id not needed
    users = [d for d in agent.get_all_users()]
    return jsonify({"users": users})

# ---------- Lesson Endpoints ----------
@app.route("/lesson/create/<user_id>", methods=["POST"])
def create_lesson(user_id):
    data = request.get_json() or {}
    context = parse_context(data)
    agent = GoalGridAgent(user_id)
    lesson = agent.create_daily_lesson({"recent_progress": context})
    return jsonify(lesson.to_dict())

@app.route("/lesson/<user_id>/<date>", methods=["GET"])
def get_lesson(user_id, date):
    agent = GoalGridAgent(user_id)
    lesson = agent.get_lesson(date)
    if lesson:
        return jsonify(lesson)
    else:
        abort(404, description="Lesson not found")

@app.route("/lesson/regenerate/<user_id>/<date>", methods=["POST"])
def regenerate_lesson(user_id, date):
    data = request.get_json() or {}
    difficulty_instructions = parse_difficulty(data)
    agent = GoalGridAgent(user_id)
    success = agent.regenerate_lesson_with_easier_tasks(date, difficulty_instructions=difficulty_instructions)
    if success:
        return jsonify({"status": "Lesson regenerated successfully"})
    else:
        abort(400, description="Failed to regenerate lesson")

# ---------- Task Endpoints ----------
@app.route("/tasks/generate/<user_id>", methods=["POST"])
def generate_tasks(user_id):
    agent = GoalGridAgent(user_id)
    lesson = agent.create_daily_lesson({})
    tasks = agent.generate_tasks_for_lesson(lesson)
    return jsonify({"tasks": [t.to_dict() for t in tasks]})

@app.route("/tasks/regenerate/<user_id>/<date>", methods=["POST"])
def regenerate_tasks(user_id, date):
    data = request.get_json() or {}
    difficulty_instructions = parse_difficulty(data)
    agent = GoalGridAgent(user_id)
    success = agent.regenerate_tasks_with_ai(date, difficulty_instructions)
    if success:
        return jsonify({"status": "Tasks regenerated successfully"})
    else:
        abort(400, description="Failed to regenerate tasks")

@app.route("/tasks/today/<user_id>", methods=["GET"])
def get_todays_tasks(user_id):
    agent = GoalGridAgent(user_id)
    tasks = agent.fetch_todays_tasks()
    return jsonify({"tasks": tasks})

@app.route("/tasks/summarize/<user_id>", methods=["GET"])
def summarize_tasks(user_id):
    agent = GoalGridAgent(user_id)
    summary = agent.summarize_todays_tasks()
    return jsonify({"summary": summary})

# ---------- Firestore Utility Endpoints ----------
@app.route("/firestore/all_users", methods=["GET"])
def firestore_all_users():
    agent = GoalGridAgent("dummy")
    return jsonify(agent.get_all_users())

@app.route("/firestore/lesson_content/<user_id>/<date>", methods=["GET"])
def firestore_lesson_content(user_id, date):
    agent = GoalGridAgent(user_id)
    lesson = agent.get_lesson(date)
    if lesson:
        return jsonify(lesson)
    else:
        abort(404, description="Lesson not found")

# ---------- Health Check ----------
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
