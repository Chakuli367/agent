import os
import json
from google.oauth2 import service_account
from google.cloud import firestore
from datetime import datetime

# ===== Read credentials from environment variable =====
credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not credentials_json:
    raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable not set")

credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_info)

# ===== Initialize Firestore Client =====
db = firestore.Client(credentials=credentials, project=credentials_info["project_id"])

# ===== GoalGridAgent Class =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id

    # Fetch a single user
    def get_user_data(self):
        doc_ref = db.collection("users").document(self.user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    # Fetch all users
    def get_all_users(self):
        users = []
        docs = db.collection("users").stream()
        for doc in docs:
            users.append(doc.to_dict())
        return users

    # Create a daily lesson
    def create_daily_lesson(self, context: dict):
        lesson_data = {
            "user_id": self.user_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "context": context,
            "tasks": [],
        }
        db.collection("lessons").document(f"{self.user_id}_{lesson_data['date']}").set(lesson_data)
        return Lesson(lesson_data)

    # Get lesson by date
    def get_lesson(self, date: str):
        doc_ref = db.collection("lessons").document(f"{self.user_id}_{date}")
        doc = doc_ref.get()
        if doc.exists:
            return Lesson(doc.to_dict()).to_dict()
        return None

    # Regenerate lesson with easier tasks
    def regenerate_lesson_with_easier_tasks(self, date: str, difficulty_instructions: str):
        lesson = self.get_lesson(date)
        if not lesson:
            return False
        lesson["context"]["difficulty_instructions"] = difficulty_instructions
        db.collection("lessons").document(f"{self.user_id}_{date}").set(lesson)
        return True

    # Task-related methods
    def generate_tasks_for_lesson(self, lesson):
        tasks = []
        for i in range(3):  # dummy tasks
            task = Task(f"Task {i+1}", lesson.to_dict()["date"])
            tasks.append(task)
        return tasks

    def regenerate_tasks_with_ai(self, date: str, difficulty_instructions: str):
        lesson = self.get_lesson(date)
        if not lesson:
            return False
        tasks = self.generate_tasks_for_lesson(Lesson(lesson))
        lesson["tasks"] = [t.to_dict() for t in tasks]
        db.collection("lessons").document(f"{self.user_id}_{date}").set(lesson)
        return True

    def fetch_todays_tasks(self):
        today = datetime.now().strftime("%Y-%m-%d")
        lesson = self.get_lesson(today)
        if not lesson:
            return []
        return lesson.get("tasks", [])

    def summarize_todays_tasks(self):
        tasks = self.fetch_todays_tasks()
        return {"total_tasks": len(tasks), "tasks": tasks}


# ===== Lesson & Task Classes =====
class Lesson:
    def __init__(self, data: dict):
        self.data = data

    def to_dict(self):
        return self.data


class Task:
    def __init__(self, description: str, date: str):
        self.description = description
        self.date = date

    def to_dict(self):
        return {"description": self.description, "date": self.date}
