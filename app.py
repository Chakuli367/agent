from flask import Flask, request, jsonify
from flask_cors import CORS
from goalgrid_agent import GoalGridAgent

app = Flask(__name__)
CORS(app)

@app.route("/todays_tasks", methods=["GET"])
def todays_tasks():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    agent = GoalGridAgent(user_id)
    tasks = agent.get_todays_tasks()
    if not tasks:
        return jsonify({"success": False, "tasks": [], "message": "No tasks found for today"}), 404
    return jsonify({"success": True, "tasks": tasks})

@app.route("/summarize_lesson", methods=["GET"])
def summarize_lesson():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    agent = GoalGridAgent(user_id)
    summary = agent.summarize_todays_lesson()
    if not summary:
        return jsonify({"success": False, "summary": "", "message": "No lesson found for today"}), 404
    return jsonify({"success": True, "summary": summary})

@app.route("/generate_tasks", methods=["POST"])
def generate_tasks():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    data = request.get_json() or {}
    instructions = data.get("difficulty_instructions", "Simplify these tasks for a beginner")

    agent = GoalGridAgent(user_id)
    success = agent.regenerate_tasks_with_ai(instructions)
    return jsonify({"success": success})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
