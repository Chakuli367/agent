import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# ===== FIRESTORE SETUP =====
from google.cloud import firestore
from google.oauth2 import service_account

SERVICE_ACCOUNT_PATH = "goalgrid.json"  # <-- your JSON key path
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
db = firestore.Client(credentials=credentials)

# ===== GROQ SETUP =====
from groq import Groq
os.environ["GSK_API_KEY"] = "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"
groq_client = Groq(api_key=os.environ.get("GSK_API_KEY"))

# ===== DATA MODELS =====
@dataclass
class Task:
    task: str
    done: bool = False

    def to_dict(self):
        return {"task": self.task, "done": self.done}

@dataclass
class Lesson:
    lesson: str
    motivation: str
    quote: str
    secret_hacks_and_shortcuts: str
    summary: str
    tasks: List[Task]
    tiny_daily_rituals_that_transform: str
    title: str
    visual_infographic_html: str

    def to_dict(self):
        data = asdict(self)
        data["tasks"] = [t.to_dict() for t in self.tasks]
        return data

# ===== AGENT =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_ref = db.collection("users").document(user_id)
        self.datedcourses_ref = self.user_ref.collection("datedcourses")

    # ---------- FIRESTORE HELPERS ----------
    def get_lesson_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetch lesson content for a given date."""
        docs = self.datedcourses_ref.stream()
        for doc in docs:
            data = doc.to_dict()
            lessons_by_date = data.get("lessons_by_date", {})
            if date in lessons_by_date:
                return lessons_by_date[date]
        return None

    def save_lesson(self, date: str, lesson: Lesson):
        """Save a lesson for a specific date."""
        doc_ref = self.datedcourses_ref.document(date)
        doc_ref.set({"lessons_by_date": {date: lesson.to_dict()}}, merge=True)
        print(f"Lesson for {date} saved!")

    # ---------- FETCH TODAY'S TASKS ----------
    def fetch_todays_tasks(self) -> List[Dict[str, Any]]:
        """Return list of tasks for today."""
        today_str = datetime.now().date().isoformat()
        lesson_data = self.get_lesson_by_date(today_str)
        if not lesson_data:
            return []
        return lesson_data.get("tasks", [])

    # ---------- AI TASK REGENERATION ----------
    def regenerate_tasks_with_ai(self, date: str, difficulty_instructions: str = "Simplify these tasks for a beginner") -> bool:
        """Use AI to regenerate lesson tasks with adjusted difficulty."""
        lesson_data = self.get_lesson_by_date(date)
        if not lesson_data:
            print(f"No lesson found for {date}")
            return False

        tasks = lesson_data.get("tasks", [])
        if not tasks:
            print(f"No tasks to regenerate for {date}")
            return False

        try:
            tasks_text = "\n".join([t["task"] for t in tasks])
            prompt = f"""
You are a helpful life coach AI. Rewrite the following tasks for a user.
Instructions: {difficulty_instructions}
Tasks:
{tasks_text}

Return a JSON list of strings, one per task.
"""
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            new_tasks_list = json.loads(content)

            lesson_data["tasks"] = [Task(task=t).to_dict() for t in new_tasks_list]
            doc_ref = self.datedcourses_ref.document(date)
            doc_ref.set({"lessons_by_date": {date: lesson_data}}, merge=True)
            print(f"Tasks for {date} regenerated successfully!")
            return True

        except Exception as e:
            print(f"Error regenerating tasks: {e}")
            return False

    # ---------- SUMMARIZE TODAY'S LESSON ----------
    def summarize_todays_lesson(self) -> Optional[List[str]]:
        """Use AI to summarize today's lesson into actionable bullet points."""
        today_str = datetime.now().date().isoformat()
        lesson_data = self.get_lesson_by_date(today_str)
        if not lesson_data:
            print("No lesson found for today.")
            return None

        try:
            prompt = f"""
You are a life coach AI. Summarize the following lesson into actionable bullet points:
Title: {lesson_data.get('title')}
Content: {lesson_data.get('lesson')}
Tasks: {json.dumps(lesson_data.get('tasks', []))}

Return a JSON list of strings.
"""
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            print(f"Error summarizing lesson: {e}")
            return None

# ====== TEST FLOW EXAMPLE ======
if __name__ == "__main__":
    agent = GoalGridAgent("G38eDqxLJSlG5AmZdf7A")

    # Fetch today's tasks
    tasks = agent.fetch_todays_tasks()
    print("Today's tasks:", tasks)

    # Regenerate tasks with AI
    today_str = datetime.now().date().isoformat()
    agent.regenerate_tasks_with_ai(today_str, difficulty_instructions="Make these tasks simpler for beginners")

    # Summarize today's lesson
    summary = agent.summarize_todays_lesson()
    print("Lesson summary:", summary)
