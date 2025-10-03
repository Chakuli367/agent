from flask import Flask, jsonify, request
from goalgrid_agent import GoalGridAgent
from datetime import datetime

app = Flask(__name__)

# For now, hardcode the user ID. In production, you can pass it as a query param or auth token.
USER_ID = "G38eDqxLJSlG5AmZdf7A"
agent = GoalGridAgent(USER_ID)


# ---------- USER DATA ----------
@app.route("/user", methods=["GET"])
def get_user_data():
    data = agent.get_user_data()
    return jsonify(data)


# ---------- LESSONS ----------
@app.route("/lesson/<date>", methods=["GET"])
def get_lesson(date):
    lesson = agent.get_lesson(date)
    if lesson:
        return jsonify(lesson)
    return jsonify({"error": "Lesson not found"}), 404


@app.route("/lesson/today", methods=["GET"])
def get_todays_lesson():
    today_str = datetime.now().date().isoformat()
    lesson = agent.get_lesson(today_str)
    if lesson:
        return jsonify(lesson)
    return jsonify({"error": "Today's lesson not found"}), 404


@app.route("/lesson/create", methods=["POST"])
def create_daily_lesson():
    context = request.json or {}
    lesson = agent.create_daily_lesson(context)
    return jsonify(asdict(lesson))


@app.route("/lesson/regenerate/<date>", methods=["POST"])
def regenerate_lesson_tasks(date):
    instructions = request.json.get("instructions", "Make these tasks simpler for beginners")
    success = agent.regenerate_tasks_with_ai(date, difficulty_instructions=instructions)
    if success:
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 400


@app.route("/lesson/summary/today", methods=["GET"])
def summarize_todays_lesson():
    summary = agent.summarize_todays_lesson()
    return jsonify(summary)


# ---------- TASKS ----------
@app.route("/tasks/today", methods=["GET"])
def fetch_todays_tasks():
    tasks = agent.fetch_todays_tasks()
    return jsonify(tasks)


@app.route("/tasks/create", methods=["POST"])
def generate_tasks():
    lesson_date = request.json.get("date")
    num_tasks = request.json.get("num_tasks", 3)
    lesson = agent.get_lesson(lesson_date)
    if not lesson:
        return jsonify({"error": "Lesson not found"}), 404
    from goalgrid_agent import Lesson
    # Rebuild Lesson object from Firestore data
    lesson_obj = Lesson(
        date=lesson_date,
        title=lesson.get("title", ""),
        content=lesson.get("lesson", ""),
        summary=lesson.get("summary", ""),
        motivation=lesson.get("motivation", ""),
        quote=lesson.get("quote", ""),
        secret_hack=lesson.get("secret_hacks_and_shortcuts", ""),
        tiny_ritual=lesson.get("tiny_daily_rituals_that_transform", ""),
        tasks=lesson.get("tasks", [])
    )
    tasks = agent.generate_tasks_for_lesson(lesson_obj, num_tasks=num_tasks)
    return jsonify([t.to_dict() for t in tasks])


# ---------- ALL USERS ----------
@app.route("/users", methods=["GET"])
def list_all_users():
    from io import StringIO
    import sys
    # Capture print statements from get_all_users
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    agent.get_all_users()
    sys.stdout = old_stdout
    output = mystdout.getvalue()
    return jsonify({"users": output})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
