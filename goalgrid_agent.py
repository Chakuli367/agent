import os
import json
from datetime import datetime
from google.oauth2 import service_account
from google.cloud import firestore
from groq import Groq

# ===== FIRESTORE SETUP =====
SERVICE_ACCOUNT_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not SERVICE_ACCOUNT_PATH:
    raise ValueError("Environment variable GOOGLE_APPLICATION_CREDENTIALS is not set.")

credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
db = firestore.Client(credentials=credentials)

# ===== GROQ SETUP =====
GROQ_API_KEY = os.environ.get("GSK_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("Environment variable GSK_API_KEY is not set.")
groq_client = Groq(api_key=GROQ_API_KEY)

class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.course_doc = db.collection("datedcourses").document(user_id)

    # --- Helper: get lessons_by_date map ---
    def _get_lessons(self):
        doc = self.course_doc.get()
        if doc.exists:
            return doc.to_dict().get("lessons_by_date", {})
        return {}

    # --- Extract today's tasks ---
    def get_todays_tasks(self):
        lessons = self._get_lessons()
        today = datetime.now().date().isoformat()
        lesson_data = lessons.get(today)
        if not lesson_data:
            return []
        return [t["task"]["task"] for t in lesson_data.get("tasks", [])]

    # --- Summarize today's lesson ---
    def summarize_todays_lesson(self):
        lessons = self._get_lessons()
        today = datetime.now().date().isoformat()
        lesson_data = lessons.get(today)
        if not lesson_data:
            return None
        return lesson_data.get("summary")

    # --- Regenerate tasks (simplify them) ---
    def regenerate_tasks_with_ai(self, difficulty_instructions: str = "Simplify these tasks for a beginner") -> bool:
        lessons = self._get_lessons()
        today = datetime.now().date().isoformat()
        lesson_data = lessons.get(today)
        if not lesson_data or not lesson_data.get("tasks"):
            print(f"No tasks found for {today}")
            return False

        try:
            tasks_text = "\n".join([t["task"]["task"] for t in lesson_data["tasks"]])
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

            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            new_tasks_list = json.loads(content)

            # Prepare updated tasks for Firestore
            updated_tasks = [{"task": {"task": t.get("title", t.get("description", ""))}, "done": False} for t in new_tasks_list]

            # Update Firestore
            lesson_data["tasks"] = updated_tasks
            self.course_doc.update({"lessons_by_date."+today: lesson_data})
            print(f"Tasks for {today} regenerated successfully!")
            return True
        except Exception as e:
            print(f"Failed to regenerate tasks: {e}")
            return False
