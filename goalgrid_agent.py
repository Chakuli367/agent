import os
import json
from datetime import datetime
from typing import List, Dict, Any
from google.cloud import firestore
from google.oauth2 import service_account

# ===== FIRESTORE INITIALIZATION =====
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not GOOGLE_CREDS_JSON:
    raise ValueError("Environment variable GOOGLE_APPLICATION_CREDENTIALS_JSON not set")

creds_dict = json.loads(GOOGLE_CREDS_JSON)
credentials = service_account.Credentials.from_service_account_info(creds_dict)
db = firestore.Client(credentials=credentials)

# ===== DATA MODELS =====
class Task:
    def __init__(self, task: str, done: bool = False):
        self.task = task
        self.done = done

    def to_dict(self):
        return {"task": self.task, "done": self.done}

class Lesson:
    def __init__(
        self,
        lesson: str,
        motivation: str,
        quote: str,
        secret_hacks_and_shortcuts: str,
        summary: str,
        tasks: List[Task],
        tiny_daily_rituals_that_transform: str,
        title: str,
        visual_infographic_html: str,
    ):
        self.lesson = lesson
        self.motivation = motivation
        self.quote = quote
        self.secret_hacks_and_shortcuts = secret_hacks_and_shortcuts
        self.summary = summary
        self.tasks = tasks
        self.tiny_daily_rituals_that_transform = tiny_daily_rituals_that_transform
        self.title = title
        self.visual_infographic_html = visual_infographic_html

    def to_dict(self):
        return {
            "lesson": self.lesson,
            "motivation": self.motivation,
            "quote": self.quote,
            "secret_hacks_and_shortcuts": self.secret_hacks_and_shortcuts,
            "summary": self.summary,
            "tasks": [t.to_dict() for t in self.tasks],
            "tiny_daily_rituals_that_transform": self.tiny_daily_rituals_that_transform,
            "title": self.title,
            "visual_infographic_html": self.visual_infographic_html,
        }

# ===== GOALGRID AGENT =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_ref = db.collection("users").document(user_id)
        self.datedcourses_col = self.user_ref.collection("datedcourses")

    # ---------- User Helpers ----------
    def get_user_data(self):
        user_doc = self.user_ref.get()
        if user_doc.exists:
            return user_doc.to_dict()
        return {}

    @staticmethod
    def get_all_users():
        users = db.collection("users").stream()
        return [u.id for u in users]

    # ---------- Lesson Helpers ----------
    def create_daily_lesson(self, context: Dict[str, Any]):
        today_str = datetime.now().strftime("%Y-%m-%d")
        lesson = Lesson(
            lesson=context.get("lesson", f"Sample lesson for {self.user_id}"),
            motivation=context.get("motivation", "Stay motivated!"),
            quote=context.get("quote", ""),
            secret_hacks_and_shortcuts=context.get("secret_hacks_and_shortcuts", ""),
            summary=context.get("summary", ""),
            tasks=[Task(task="Sample task 1"), Task(task="Sample task 2")],
            tiny_daily_rituals_that_transform=context.get("tiny_daily_rituals_that_transform", ""),
            title=context.get("title", f"Lesson {today_str}"),
            visual_infographic_html=context.get("visual_infographic_html", ""),
        )
        self.datedcourses_col.document(today_str).set(lesson.to_dict())
        return lesson

    def get_lesson(self, date: str):
        doc = self.datedcourses_col.document(date).get()
        if doc.exists:
            data = doc.to_dict()
            tasks = [Task(**t) for t in data.get("tasks", [])]
            return Lesson(
                lesson=data.get("lesson", ""),
                motivation=data.get("motivation", ""),
                quote=data.get("quote", ""),
                secret_hacks_and_shortcuts=data.get("secret_hacks_and_shortcuts", ""),
                summary=data.get("summary", ""),
                tasks=tasks,
                tiny_daily_rituals_that_transform=data.get("tiny_daily_rituals_that_transform", ""),
                title=data.get("title", ""),
                visual_infographic_html=data.get("visual_infographic_html", ""),
            ).to_dict()
        return None

    def regenerate_lesson_with_easier_tasks(self, date: str, difficulty_instructions: str):
        lesson = self.get_lesson(date)
        if not lesson:
            return False
        # Simplify tasks for easier completion
        for t in lesson["tasks"]:
            t["task"] = f"{difficulty_instructions}: {t['task']}"
        self.datedcourses_col.document(date).update({"tasks": lesson["tasks"]})
        return True

    # ---------- Task Helpers ----------
    def generate_tasks_for_lesson(self, lesson: Lesson):
        # In reality this would call AI to generate tasks
        return lesson.tasks

    def regenerate_tasks_with_ai(self, date: str, difficulty_instructions: str):
        lesson = self.get_lesson(date)
        if not lesson:
            return False
        for t in lesson["tasks"]:
            t["task"] = f"{difficulty_instructions}: {t['task']}"
        self.datedcourses_col.document(date).update({"tasks": lesson["tasks"]})
        return True

    def fetch_todays_tasks(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        lesson = self.get_lesson(today_str)
        return lesson.get("tasks", []) if lesson else []

    def summarize_todays_tasks(self):
        tasks = self.fetch_todays_tasks()
        summary = "\n".join([f"- {t['task']} (Done: {t['done']})" for t in tasks])
        return summary
