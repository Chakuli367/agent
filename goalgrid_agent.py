import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.cloud import firestore
from google.oauth2 import service_account
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

# ===== DATA MODELS =====
class Task:
    def __init__(self, title: str, description: str):
        self.done = False
        self.task = {"task": description}
        self.title = title

    def to_dict(self):
        return {"done": self.done, "task": self.task}

class Lesson:
    def __init__(self, date: str, title: str, lesson: str, summary: str, motivation: str,
                 quote: str, secret_hacks_and_shortcuts: str, tiny_daily_rituals_that_transform: str,
                 visual_infographic_html: str, tasks: List[Task] = None):
        self.date = date
        self.title = title
        self.lesson = lesson
        self.summary = summary
        self.motivation = motivation
        self.quote = quote
        self.secret_hacks_and_shortcuts = secret_hacks_and_shortcuts
        self.tiny_daily_rituals_that_transform = tiny_daily_rituals_that_transform
        self.visual_infographic_html = visual_infographic_html
        self.tasks = [t.to_dict() for t in tasks] if tasks else []

    def to_dict(self):
        return {
            "title": self.title,
            "lesson": self.lesson,
            "summary": self.summary,
            "motivation": self.motivation,
            "quote": self.quote,
            "secret_hacks_and_shortcuts": self.secret_hacks_and_shortcuts,
            "tiny_daily_rituals_that_transform": self.tiny_daily_rituals_that_transform,
            "visual_infographic_html": self.visual_infographic_html,
            "tasks": self.tasks
        }

# ===== AGENT =====
class GoalGridAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_ref = db.collection('users').document(user_id)
        self.dated_courses_ref = self.user_ref.collection('dated_courses')
        self.active_course_doc = None

    # ---------- FIRESTORE HELPERS ----------
    def get_user_data(self) -> Dict[str, Any]:
        doc = self.user_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            default_data = {"created_at": datetime.now().isoformat(), "total_lessons_completed": 0}
            self.user_ref.set(default_data)
            return default_data

    def save_course(self, lessons: List[Lesson]):
        doc_ref = self.dated_courses_ref.document()
        content = {
            "joined_date": datetime.now().date().isoformat(),
            "lessons_by_date": {lesson.date: lesson.to_dict() for lesson in lessons}
        }
        doc_ref.set({"content": content})
        self.active_course_doc = doc_ref
        print(f"Course saved successfully at users/{self.user_id}/dated_courses/{doc_ref.id}")

    def get_active_course(self):
        if self.active_course_doc:
            return self.active_course_doc.get().to_dict().get("content", {})
        docs = list(self.dated_courses_ref.stream())
        if not docs:
            return {}
        latest_doc = sorted(docs, key=lambda d: d.create_time, reverse=True)[0]
        self.active_course_doc = self.dated_courses_ref.document(latest_doc.id)
        return latest_doc.to_dict().get("content", {})

    def update_course_content(self, lessons_by_date: Dict[str, Any]):
        if not self.active_course_doc:
            print("No active course document. Creating one.")
            self.save_course([])  # empty course to create doc
        content = self.get_active_course()
        content["lessons_by_date"] = lessons_by_date
        self.active_course_doc.set({"content": content})
        print("Course content updated.")

    # ---------- FETCH LESSON BY DATE ----------
    def get_lesson(self, date: str) -> dict:
        course_content = self.get_active_course()
        lessons = course_content.get("lessons_by_date", {})
        return lessons.get(date)

    # ---------- CONTENT GENERATION ----------
    def generate_personalized_content(self, context: Dict[str, Any]) -> Dict[str, str]:
        try:
            prompt = f"""
You are a supportive AI mentor. Generate a lesson for a user.
Recent progress: {context.get('recent_progress', 'Just starting')}
Return JSON with keys: title, lesson, summary, motivation, quote, secret_hacks_and_shortcuts, tiny_daily_rituals_that_transform, visual_infographic_html
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
                "title": "Sample Lesson",
                "lesson": "This is a sample lesson content.",
                "summary": "Sample summary.",
                "motivation": "Keep going!",
                "quote": "Consistency is key.",
                "secret_hacks_and_shortcuts": "Start small.",
                "tiny_daily_rituals_that_transform": "Take 5 minutes daily.",
                "visual_infographic_html": "<div>Sample Infographic</div>"
            }

    # ---------- LESSON & TASK CREATION ----------
    def create_daily_lesson(self, context: Dict[str, Any] = {}) -> Lesson:
        today_str = datetime.now().date().isoformat()
        content = self.generate_personalized_content(context)
        lesson = Lesson(
            date=today_str,
            title=content["title"],
            lesson=content["lesson"],
            summary=content["summary"],
            motivation=content["motivation"],
            quote=content["quote"],
            secret_hacks_and_shortcuts=content["secret_hacks_and_shortcuts"],
            tiny_daily_rituals_that_transform=content["tiny_daily_rituals_that_transform"],
            visual_infographic_html=content["visual_infographic_html"],
            tasks=[]
        )
        course_content = self.get_active_course()
        lessons = course_content.get("lessons_by_date", {})
        lessons[today_str] = lesson.to_dict()
        self.update_course_content(lessons)
        return lesson

    def generate_tasks_for_lesson(self, lesson: Lesson, num_tasks: int = 3) -> List[Task]:
        tasks = []
        for i in range(1, num_tasks + 1):
            t = Task(
                title=f"Step {i}",
                description=f"Complete step {i} for '{lesson.title}'"
            )
            lesson.tasks.append(t.to_dict())
            tasks.append(t)
        course_content = self.get_active_course()
        lessons = course_content.get("lessons_by_date", {})
        lessons[lesson.date] = lesson.to_dict()
        self.update_course_content(lessons)
        return tasks

    # ---------- REGENERATE TASKS USING AI ----------
    def regenerate_tasks_with_ai(self, date: str, difficulty_instructions: str = "Simplify these tasks for a beginner") -> bool:
        course_content = self.get_active_course()
        lessons = course_content.get("lessons_by_date", {})
        lesson_data = lessons.get(date)
        if not lesson_data:
            print(f"No lesson found for {date}")
            return False

        tasks = lesson_data.get("tasks", [])
        if not tasks:
            print(f"No tasks to regenerate for {date}")
            return False

        try:
            tasks_text = "\n".join([f"{i+1}. {t['task']['task']}" for i, t in enumerate(tasks)])
            prompt = f"""
You are a helpful life coach AI. Rewrite the following tasks for a user.
Instructions: {difficulty_instructions}
Tasks:
{tasks_text}

Return JSON with list of tasks as: {{title, description}}
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
                updated_task = Task(title=t.get("title", f"Step {i}"), description=t.get("description", f"Complete step {i}"))
                updated_tasks.append(updated_task.to_dict())

            lesson_data["tasks"] = updated_tasks
            lessons[date] = lesson_data
            self.update_course_content(lessons)
            print(f"Lesson {date} tasks regenerated successfully using AI!")
            return True
        except Exception as e:
            print(f"Failed to regenerate tasks: {e}")
            return False

    # ---------- FETCH TODAY'S TASKS ----------
    def get_todays_tasks(self) -> List[Dict[str, Any]]:
        today_str = datetime.now().date().isoformat()
        course_content = self.get_active_course()
        lesson_data = course_content.get("lessons_by_date", {}).get(today_str)
        if lesson_data:
            return lesson_data.get("tasks", [])
        else:
            print(f"No lesson found for today ({today_str})")
            return []

    # ---------- SUMMARIZE TODAY'S LESSON ----------
    def summarize_todays_lesson(self) -> Optional[List[str]]:
        today_str = datetime.now().date().isoformat()
        course_content = self.get_active_course()
        lesson_data = course_content.get("lessons_by_date", {}).get(today_str)
        if not lesson_data:
            print(f"No lesson found for today ({today_str})")
            return None

        try:
            content_text = f"{lesson_data['title']}\n{lesson_data['lesson']}\nTasks:\n" + \
                           "\n".join([f"{i+1}. {t['task']['task']}" for i, t in enumerate(lesson_data.get("tasks", []))])
            prompt = f"""
You are a helpful AI assistant. Summarize today's lesson into a concise list of task descriptions.
Lesson content:
{content_text}

Return JSON: list of task descriptions only.
"""
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert life coach. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            print(f"Failed to summarize lesson: {e}")
            return None
