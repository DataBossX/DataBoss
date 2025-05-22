"""
Todo Master for DataBoss
Manages system tasks and improvements
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("databoss.todo_master")
logging.basicConfig(level=logging.INFO)

class TodoMaster:
    def __init__(self, todo_file: str = "todo_list.json"):
        self.todo_file = todo_file
        self.todos = self.load_todos()
        
    def load_todos(self) -> List[Dict[str, Any]]:
        """Load todos from file"""
        if os.path.exists(self.todo_file):
            try:
                with open(self.todo_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load todos: {str(e)}")
                return []
        return []
        
    def save_todos(self) -> bool:
        """Save todos to file"""
        try:
            with open(self.todo_file, "w") as f:
                json.dump(self.todos, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save todos: {str(e)}")
            return False
            
    def add_todo(self, title: str, description: str, priority: int = 1, 
                category: str = "general") -> Dict[str, Any]:
        """Add a new todo item"""
        todo = {
            "id": int(time.time()),
            "title": title,
            "description": description,
            "priority": priority,
            "category": category,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.todos.append(todo)
        self.save_todos()
        logger.info(f"Added todo: {title}")
        return todo
        
    def update_todo(self, todo_id: int, status: str, notes: Optional[str] = None) -> bool:
        """Update a todo item"""
        for todo in self.todos:
            if todo.get("id") == todo_id:
                todo["status"] = status
                todo["updated_at"] = datetime.now().isoformat()
                if notes:
                    todo["notes"] = notes
                self.save_todos()
                logger.info(f"Updated todo {todo_id} to {status}")
                return True
                
        logger.warning(f"Todo {todo_id} not found")
        return False
        
    def get_pending_todos(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending todos, optionally filtered by category"""
        pending = [todo for todo in self.todos if todo.get("status") == "pending"]
        
        if category:
            pending = [todo for todo in pending if todo.get("category") == category]
            
        return sorted(pending, key=lambda x: x.get("priority", 0), reverse=True)
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate a report of todo status"""
        categories = {}
        statuses = {"pending": 0, "in_progress": 0, "completed": 0, "cancelled": 0}
        
        for todo in self.todos:
            category = todo.get("category", "general")
            status = todo.get("status", "pending")
            
            if category not in categories:
                categories[category] = {"total": 0, "pending": 0, "completed": 0}
                
            categories[category]["total"] += 1
            categories[category][status] = categories[category].get(status, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
            
        return {
            "total_todos": len(self.todos),
            "by_status": statuses,
            "by_category": categories,
            "generated_at": datetime.now().isoformat()
        }
