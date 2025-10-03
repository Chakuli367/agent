from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from goalgrid_agent import GoalGridAgent, Lesson, Task
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="GoalGrid Backend API")

# Allow CORS for all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== REQUEST MODELS =====
class ContextModel(BaseModel):
    recent_progress: Optional[str] = None

class DifficultyModel(BaseModel):
    difficulty_instructions: Optional[str] = "Make these tasks simpler and easier to complete for a beginner"

# ===== ENDPOINTS =====

@app.get("/")
def root():
    return {"status": "GoalGrid Backend is running!"}

# ---------- User Helpers ----------
@app.get("/user/{user_id}")
def get_user(user_id: str):
    agent = GoalGridAgent(user_id)
    return agent.get_user_data()

@app.get("/users")
def get_all_users():
    agent = GoalGridAgent("dummy")  # user_id not needed
    users = []
    for d in agent.get_all_users():
        users.append(d)
    return {"users": users}

# ---------- Lesson Endpoints ----------
@app.post("/lesson/create/{user_id}")
def create_lesson(user_id: str, context: ContextModel):
    agent = GoalGridAgent(user_id)
    lesson = agent.create_daily_lesson(context.dict())
    return lesson.to_dict()

@app.get("/lesson/{user_id}/{date}")
def get_lesson(user_id: str, date: str):
    agent = GoalGridAgent(user_id)
    lesson = agent.get_lesson(date)
    if lesson:
        return lesson
    else:
        raise HTTPException(status_code=404, detail="Lesson not found")

@app.post("/lesson/regenerate/{user_id}/{date}")
def regenerate_lesson(user_id: str, date: str, difficulty: DifficultyModel):
    agent = GoalGridAgent(user_id)
    success = agent.regenerate_lesson_with_easier_tasks(date, difficulty_instructions=difficulty.difficulty_instructions)
    if success:
        return {"status": "Lesson regenerated successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to regenerate lesson")

# ---------- Task Endpoints ----------
@app.post("/tasks/generate/{user_id}")
def generate_tasks(user_id: str):
    agent = GoalGridAgent(user_id)
    lesson = agent.create_daily_lesson({})
    tasks = agent.generate_tasks_for_lesson(lesson)
    return {"tasks": [t.to_dict() for t in tasks]}

@app.post("/tasks/regenerate/{user_id}/{date}")
def regenerate_tasks(user_id: str, date: str, difficulty: DifficultyModel):
    agent = GoalGridAgent(user_id)
    success = agent.regenerate_tasks_with_ai(date, difficulty.difficulty_instructions)
    if success:
        return {"status": "Tasks regenerated successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to regenerate tasks")

@app.get("/tasks/today/{user_id}")
def get_todays_tasks(user_id: str):
    agent = GoalGridAgent(user_id)
    tasks = agent.fetch_todays_tasks()
    return {"tasks": tasks}

@app.get("/tasks/summarize/{user_id}")
def summarize_tasks(user_id: str):
    agent = GoalGridAgent(user_id)
    summary = agent.summarize_todays_tasks()
    return {"summary": summary}

# ---------- Firestore Utility Endpoints ----------
@app.get("/firestore/all_users")
def firestore_all_users():
    agent = GoalGridAgent("dummy")
    return agent.get_all_users()

@app.get("/firestore/lesson_content/{user_id}/{date}")
def firestore_lesson_content(user_id: str, date: str):
    agent = GoalGridAgent(user_id)
    lesson = agent.get_lesson(date)
    if lesson:
        return lesson
    else:
        raise HTTPException(status_code=404, detail="Lesson not found")

# ---------- Health Check ----------
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
