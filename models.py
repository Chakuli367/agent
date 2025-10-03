from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

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
