import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.cloud import firestore
from google.oauth2 import service_account
from groq import Groq
from models import Task, Lesson

# ===== FIRESTORE SETUP =====
# Expecting RENDER_ENV variable FIRESTORE_CREDENTIALS_JSON (full JSON string)
firestore_credentials_json = os.environ.get("FIRESTORE_CREDENTIALS_JSON")
if not firestore_credentials_json:
    raise Exception("FIRESTORE_CREDENTIALS_JSON not set in environment variables")

credentials_info = json.loads(firestore_credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
db = firestore.Client(credentials=credentials)

# ===== GROQ SETUP =====
# Expecting RENDER_ENV variable GROQ_API_KEY
groq_api_key = os.environ.get("GROQ_API_KEY")
if not groq_api_key:
    raise Exception("GROQ_API_KEY not set in environment variables")

groq_client = Groq(api_key=groq_api_key)

# ===== AGENT CLASS =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_ref = db.collection('users').document(user_id)
        self.lessons_ref = self.user_ref.collection('lessons_by_date')

    # ---------- FIRESTORE HELPERS ----------
    def get_user_data(self) -> Dict[str, Any]:
        doc = self.user_ref.get()
        if doc.exists:
            return doc.to_dict()
        default_data = {
            'created_at': datetime.now().isoformat(),
            'total_lessons_completed': 0,
            'current_streak': 0,
            'goals': []
        }
        self.user_ref.set(default_data)
        return default_data

    def save_lesson(self, lesson: Lesson):
        self.lessons_ref.document(lesson.date).set(asdict(lesson), merge=True)
        print(f"Lesson {lesson.date} saved successfully!")

    def get_lesson(self, date: str) -> Optional[Dict[str, Any]]:
        doc = self.lessons_ref.document(date).get()
        return doc.to_dict() if doc.exists else None

    def get_all_users(self):
        docs = db.collection('users').stream()
        return [{d.id: d.to_dict()} for d in docs]

    # ---------- CONTENT GENERATION ----------
    def generate_personalized_content(self, context: Dict[str, Any]) -> Dict[str, str]:
        try:
            user_data = self.get_user_data()
            prompt = f"""
You are a supportive AI mentor. Generate a lesson for a user.
User goals: {', '.join(user_data.get('goals', ['general']))}
Recent progress: {context.get('recent_progress', 'Just starting')}
Return JSON: lesson_title, lesson_content, summary, motivation, quote, secret_hack, tiny_ritual
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
            return json.loads(content)
        except:
            return {
                "lesson_title": "Building Consistent Habits",
                "lesson_content": "Focus on creating small, sustainable habits.",
                "summary": "Take small steps every day.",
                "motivation": "Every step counts!",
                "quote": "Consistency beats intensity.",
                "secret_hack": "Start with 2-minute micro-habits.",
                "tiny_ritual": "Deep breath before starting."
            }

    # ---------- LESSON & TASK CREATION ----------
    def create_daily_lesson(self, context: Dict[str, Any] = {}) -> Lesson:
        today_str = datetime.now().date().isoformat()
        lesson_content = self.generate_personalized_content(context)
        lesson = Lesson(
            date=today_str,
            title=lesson_content["lesson_title"],
            content=lesson_content["lesson_content"],
            summary=lesson_content["summary"],
            motivation=lesson_content["motivation"],
            quote=lesson_content["quote"],
            secret_hack=lesson_content["secret_hack"],
            tiny_ritual=lesson_content["tiny_ritual"],
            tasks=[]
        )
        self.save_lesson(lesson)
        return lesson

    def generate_tasks_for_lesson(self, lesson: Lesson, num_tasks: int = 3) -> List[Task]:
        tasks = []
        for i in range(1, num_tasks + 1):
            t = Task(
                id=f"{lesson.date}-task-{i}",
                title=f"Step {i}",
                description=f"Complete step {i} for '{lesson.title}'",
                completed=False,
                priority=i,
                created_at=datetime.now().isoformat()
            )
            lesson.tasks.append(t.to_dict())
            tasks.append(t)
        self.save_lesson(lesson)
        return tasks

    # ---------- AI-POWERED TASK REGENERATION ----------
    def regenerate_tasks_with_ai(self, date: str, difficulty_instructions: str = "Simplify these tasks for a beginner") -> bool:
        lesson_data = self.get_lesson(date)
        if not lesson_data or not lesson_data.get("tasks"):
            return False

        try:
            tasks_text = "\n".join([f"{t['title']}: {t['description']}" for t in lesson_data["tasks"]])
            prompt = f"""
Rewrite these tasks for a user with the following instructions: {difficulty_instructions}
Tasks:
{tasks_text}
Return JSON list of tasks with 'title' and 'description'.
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
            updated_tasks = []
            for i, t in enumerate(new_tasks_list, 1):
                updated_task = Task(
                    id=f"{date}-task-{i}",
                    title=t.get("title", f"Step {i}"),
                    description=t.get("description", f"Complete step {i}"),
                    completed=False,
                    priority=i,
                    created_at=datetime.now().isoformat()
                )
                updated_tasks.append(updated_task.to_dict())

            lesson_data["tasks"] = updated_tasks
            self.lessons_ref.document(date).set(lesson_data, merge=True)
            return True
        except Exception as e:
            print(f"Error regenerating tasks: {e}")
            return False

    # ---------- SUMMARIZE TODAY'S TASKS USING AI ----------
    def summarize_todays_tasks(self, date: str) -> str:
        lesson_data = self.get_lesson(date)
        if not lesson_data or not lesson_data.get("tasks"):
            return "No tasks found for today."

        tasks_text = "\n".join([f"- {t['title']}: {t['description']}" for t in lesson_data["tasks"]])
        prompt = f"Summarize the following tasks in a concise, motivating way:\n{tasks_text}"

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            summary = response.choices[0].message.content.strip()
            return summary
        except Exception as e:
            print(f"Error summarizing tasks: {e}")
            return "Could not generate summary."
