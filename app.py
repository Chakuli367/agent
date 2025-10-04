import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from google.cloud import firestore
from groq import Groq

# ===== FIRESTORE SETUP =====
SERVICE_ACCOUNT_JSON = os.environ.get("GOALGRID_SA_JSON")
if not SERVICE_ACCOUNT_JSON:
    raise ValueError("Environment variable GOALGRID_SA_JSON is not set!")

credentials = service_account.Credentials.from_service_account_info(
    json.loads(SERVICE_ACCOUNT_JSON)
)

db = firestore.Client(credentials=credentials, project=credentials.project_id)

# ===== GROQ SETUP =====
GROQ_API_KEY = os.environ.get("GSK_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("Environment variable GSK_API_KEY is not set.")
groq_client = Groq(api_key=GROQ_API_KEY)

# ===== AGENT =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Collection structure: users/<uid>/datedcourses/<randomdoc>
        self.user_collection = db.collection("users").document(user_id).collection("datedcourses")

    def _get_lessons(self):
        # Fetch all datedcourses docs and merge their lessons_by_date
        lessons_by_date = {}
        docs = self.user_collection.stream()
        for doc in docs:
            data = doc.to_dict()
            if "lessons_by_date" in data:
                lessons_by_date.update(data["lessons_by_date"])
        return lessons_by_date

    def get_todays_tasks(self, date: str = None):
        lessons = self._get_lessons()
        if not date:
            date = datetime.now().date().isoformat()
        lesson_data = lessons.get(date)
        if not lesson_data or not lesson_data.get("tasks"):
            return []

        tasks_list = lesson_data.get("tasks", [])
        tasks = []
        for t in tasks_list:
            if isinstance(t, dict):
                tasks.append(t.get("task", {}).get("task", ""))
            elif isinstance(t, str):
                tasks.append(t)
        return tasks

    def summarize_todays_lesson(self, date: str = None):
        lessons = self._get_lessons()
        if not date:
            date = datetime.now().date().isoformat()
        lesson_data = lessons.get(date)
        if not lesson_data:
            return None
        return lesson_data.get("summary")

    def regenerate_tasks_with_ai(self, difficulty_instructions: str = "Simplify these tasks for a beginner", date: str = None) -> bool:
        lessons = self._get_lessons()
        if not date:
            date = datetime.now().date().isoformat()
        lesson_data = lessons.get(date)
        if not lesson_data or not lesson_data.get("tasks"):
            print(f"No tasks found for {date}")
            return False

        try:
            tasks_text = "\n".join([t["task"]["task"] if isinstance(t, dict) else t for t in lesson_data["tasks"]])
            prompt = f"""
You are a helpful life coach AI. Rewrite the following tasks for a user.
Instructions: {difficulty_instructions}
Tasks:
{tasks_text}

Return JSON as list of tasks with 'title' and 'description'.
"""
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            new_tasks_list = json.loads(content)
            updated_tasks = [{"task": {"task": t.get("title", t.get("description", ""))}, "done": False} for t in new_tasks_list]

            # Update the first document in datedcourses (simplest approach)
            docs = list(self.user_collection.stream())
            if docs:
                doc_ref = self.user_collection.document(docs[0].id)
                doc_ref.update({"lessons_by_date."+date: {**lesson_data, "tasks": updated_tasks}})
                print(f"Tasks for {date} regenerated successfully!")
                return True
            else:
                print("No datedcourses document found to update tasks.")
                return False
        except Exception as e:
            print(f"Failed to regenerate tasks: {e}")
            return False

# ===== FLASK APP =====
app = Flask(__name__)
CORS(app)

@app.route("/todays_tasks", methods=["GET"])
def todays_tasks():
    user_id = request.args.get("user_id")
    date = request.args.get("date")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    agent = GoalGridAgent(user_id)
    tasks = agent.get_todays_tasks(date)
    if not tasks:
        return jsonify({"success": False, "tasks": [], "message": "No tasks found for this date"}), 404
    return jsonify({"success": True, "tasks": tasks})

@app.route("/summarize_lesson", methods=["GET"])
def summarize_lesson():
    user_id = request.args.get("user_id")
    date = request.args.get("date")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    agent = GoalGridAgent(user_id)
    summary = agent.summarize_todays_lesson(date)
    if not summary:
        return jsonify({"success": False, "summary": "", "message": "No lesson found for this date"}), 404
    return jsonify({"success": True, "summary": summary})

@app.route("/generate_tasks", methods=["POST"])
def generate_tasks():
    user_id = request.args.get("user_id")
    date = request.args.get("date")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id parameter"}), 400

    data = request.get_json() or {}
    instructions = data.get("difficulty_instructions", "Simplify these tasks for a beginner")

    agent = GoalGridAgent(user_id)
    success = agent.regenerate_tasks_with_ai(instructions, date)
    return jsonify({"success": success})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
