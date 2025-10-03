import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# ===== FIRESTORE SETUP =====
from google.cloud import firestore
from google.oauth2 import service_account

SERVICE_ACCOUNT_PATH = os.environ.get("GOALGRID_SERVICE_ACCOUNT", "goalgrid.json")
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
db = firestore.Client(credentials=credentials)

# ===== GROQ SETUP =====
from groq import Groq
groq_client = Groq(api_key=os.environ.get("GSK_API_KEY"))

# ===== DATA MODELS =====
@dataclass
class Task:
    id: str
    title: str
    description: str
    completed: bool
    priority: int
    created_at: str
    due_date: Optional[str] = None
    tags: List[str] = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class Lesson:
    date: str
    title: str
    content: str
    tasks: List[Dict[str, Any]]
    summary: str
    motivation: str
    quote: str
    secret_hack: str
    tiny_ritual: str
    completed: bool = False
    progress_percentage: int = 0

# ===== AGENT =====
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
        else:
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

    def get_all_users(self) -> List[str]:
        docs = db.collection('users').stream()
        return [d.id for d in docs]

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
            # fallback content
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
        if not lesson_data:
            print(f"No lesson found for {date}")
            return False
        tasks = lesson_data.get("tasks", [])
        if not tasks:
            print(f"No tasks to regenerate for {date}")
            return False
        try:
            tasks_text = "\n".join([f"{t['title']}: {t['description']}" for t in tasks])
            prompt = f"""
You are a helpful life coach AI. Rewrite the following tasks for a user.
Instructions: {difficulty_instructions}
Tasks:
{tasks_text}

Return JSON with the same structure: list of {{title, description}}.
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
            print(f"Lesson {date} tasks regenerated successfully using AI!")
            return True
        except Exception as e:
            print(f"Failed to regenerate tasks: {e}")
            return False

    # ---------- FETCH TODAY'S TASKS ----------
    def fetch_todays_tasks(self) -> List[Dict[str, Any]]:
        today_str = datetime.now().date().isoformat()
        lesson_data = self.get_lesson(today_str)
        if lesson_data and "tasks" in lesson_data:
            return lesson_data["tasks"]
        return []

    # ---------- SUMMARIZE TODAY'S TASKS ----------
    def summarize_todays_tasks(self) -> str:
        tasks = self.fetch_todays_tasks()
        if not tasks:
            return "No tasks for today."
        tasks_text = "\n".join([f"{t['title']}: {t['description']}" for t in tasks])
        prompt = f"""
Summarize the following tasks concisely for a user in a motivating way:
{tasks_text}
"""
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach. Respond concisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            summary = response.choices[0].message.content.strip()
            return summary
        except:
            return "You have tasks to complete today. Stay focused and motivated!"

