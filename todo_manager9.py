"""
DataBossX To-Do Manager v9
SQLite-based task orchestrator with AI-powered prioritization
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

from config_databossx9 import get_config

# Configure logging
logger = logging.getLogger(__name__)


class TodoManager:
    """
    Manages tasks and provides AI-powered prioritization.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize Todo Manager.

        Args:
            db_path: Path to SQLite database (optional, uses config default)
        """
        config = get_config()
        self.db_path = db_path or config.get('paths', 'tasks_database', 'databossx_tasks.db')
        self.projects = config.get('tasks', 'projects', [])
        self.priority_levels = config.get('tasks', 'priority_levels', [])
        self.status_options = config.get('tasks', 'status_options', [])
        self._init_database()
        logger.info(f"TodoManager initialized with database: {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database with tasks table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    project TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assigned_agent TEXT,
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    tags TEXT,
                    dependencies TEXT,
                    ai_score REAL DEFAULT 0.0,
                    notes TEXT
                )
            """)

            # Create task history table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            """)

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_project ON tasks(project)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_score ON tasks(ai_score)")

            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def add_task(self, title: str, description: str = "", project: str = "General",
                 priority: str = "Medium", status: str = "To Do",
                 assigned_agent: Optional[str] = None, due_date: Optional[str] = None,
                 tags: Optional[List[str]] = None) -> int:
        """
        Add a new task.

        Args:
            title: Task title
            description: Task description
            project: Project name
            priority: Priority level
            status: Task status
            assigned_agent: Assigned agent name
            due_date: Due date (ISO format)
            tags: List of tags

        Returns:
            Task ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()
            tags_json = json.dumps(tags) if tags else None

            cursor.execute("""
                INSERT INTO tasks (title, description, project, priority, status,
                                 assigned_agent, due_date, created_at, updated_at, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, project, priority, status, assigned_agent,
                  due_date, now, now, tags_json))

            task_id = cursor.lastrowid

            # Log task creation
            self._log_history(cursor, task_id, "created", None, title)

            conn.commit()
            conn.close()

            logger.info(f"Task created: {task_id} - {title}")
            return task_id

        except Exception as e:
            logger.error(f"Error adding task: {e}")
            raise

    def update_task(self, task_id: int, **updates) -> bool:
        """
        Update task fields.

        Args:
            task_id: Task ID
            **updates: Fields to update

        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get current task for history
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            old_task = cursor.fetchone()
            if not old_task:
                return False

            # Build update query
            valid_fields = ['title', 'description', 'project', 'priority', 'status',
                          'assigned_agent', 'due_date', 'tags', 'dependencies', 'notes']
            update_fields = {k: v for k, v in updates.items() if k in valid_fields}

            if not update_fields:
                return False

            # Handle status change to "Done"
            if update_fields.get('status') == 'Done':
                update_fields['completed_at'] = datetime.now().isoformat()

            update_fields['updated_at'] = datetime.now().isoformat()

            # Construct SQL
            set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [task_id]

            cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)

            # Log changes
            for field, new_value in update_fields.items():
                if field != 'updated_at':
                    self._log_history(cursor, task_id, f"updated_{field}",
                                    str(old_task), str(new_value))

            conn.commit()
            conn.close()

            logger.info(f"Task updated: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            return False

    def delete_task(self, task_id: int) -> bool:
        """
        Delete a task.

        Args:
            task_id: Task ID

        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._log_history(cursor, task_id, "deleted", None, None)

            conn.commit()
            conn.close()

            logger.info(f"Task deleted: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task dictionary or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return None

    def get_tasks(self, project: Optional[str] = None, status: Optional[str] = None,
                  priority: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tasks with optional filtering.

        Args:
            project: Filter by project
            status: Filter by status
            priority: Filter by priority
            limit: Maximum number of tasks

        Returns:
            List of task dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM tasks WHERE 1=1"
            params = []

            if project:
                query += " AND project = ?"
                params.append(project)
            if status:
                query += " AND status = ?"
                params.append(status)
            if priority:
                query += " AND priority = ?"
                params.append(priority)

            query += " ORDER BY ai_score DESC, priority DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    def calculate_ai_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate AI priority score for a task (0-100).
        Higher score = more important/urgent.

        Args:
            task: Task dictionary

        Returns:
            AI score (0-100)
        """
        score = 0.0

        # Priority weight (0-40 points)
        priority_map = {"Critical": 40, "High": 30, "Medium": 20, "Low": 10}
        score += priority_map.get(task.get('priority', 'Medium'), 20)

        # Status weight (0-20 points)
        status_map = {"Blocked": 20, "In Progress": 15, "To Do": 10, "Done": 0}
        score += status_map.get(task.get('status', 'To Do'), 10)

        # Age weight (0-20 points)
        try:
            created_at = datetime.fromisoformat(task.get('created_at', datetime.now().isoformat()))
            age_days = (datetime.now() - created_at).days
            age_score = min(20, age_days * 2)  # Cap at 20 points
            score += age_score
        except:
            pass

        # Due date urgency (0-20 points)
        if task.get('due_date'):
            try:
                due_date = datetime.fromisoformat(task['due_date'])
                days_until_due = (due_date - datetime.now()).days
                if days_until_due < 0:
                    score += 20  # Overdue
                elif days_until_due <= 1:
                    score += 15  # Due today/tomorrow
                elif days_until_due <= 7:
                    score += 10  # Due this week
                elif days_until_due <= 30:
                    score += 5   # Due this month
            except:
                pass

        return min(100.0, score)

    def update_all_ai_scores(self):
        """Recalculate AI scores for all tasks"""
        try:
            tasks = self.get_tasks(limit=1000)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for task in tasks:
                score = self.calculate_ai_score(task)
                cursor.execute("UPDATE tasks SET ai_score = ? WHERE id = ?",
                             (score, task['id']))

            conn.commit()
            conn.close()
            logger.info("AI scores updated for all tasks")

        except Exception as e:
            logger.error(f"Error updating AI scores: {e}")

    def get_next_best_move(self) -> Optional[Dict[str, Any]]:
        """
        Get the next best task to work on based on AI scoring.

        Returns:
            Task dictionary or None
        """
        try:
            self.update_all_ai_scores()
            tasks = self.get_tasks(status="To Do", limit=1)
            if tasks:
                return tasks[0]

            # If no "To Do" tasks, check "In Progress"
            tasks = self.get_tasks(status="In Progress", limit=1)
            return tasks[0] if tasks else None

        except Exception as e:
            logger.error(f"Error getting next best move: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get task statistics.

        Returns:
            Statistics dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Total tasks
            cursor.execute("SELECT COUNT(*) FROM tasks")
            stats['total_tasks'] = cursor.fetchone()[0]

            # By status
            cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
            stats['by_status'] = dict(cursor.fetchall())

            # By project
            cursor.execute("SELECT project, COUNT(*) FROM tasks GROUP BY project")
            stats['by_project'] = dict(cursor.fetchall())

            # By priority
            cursor.execute("SELECT priority, COUNT(*) FROM tasks GROUP BY priority")
            stats['by_priority'] = dict(cursor.fetchall())

            # Completion rate
            total = stats['total_tasks']
            done = stats['by_status'].get('Done', 0)
            stats['completion_rate'] = (done / total * 100) if total > 0 else 0

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def _log_history(self, cursor, task_id: int, action: str,
                     old_value: Optional[str], new_value: Optional[str]):
        """Log task change to history"""
        try:
            cursor.execute("""
                INSERT INTO task_history (task_id, action, old_value, new_value, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, action, old_value, new_value, "system", datetime.now().isoformat()))
        except Exception as e:
            logger.error(f"Error logging history: {e}")

    def search_tasks(self, query: str) -> List[Dict[str, Any]]:
        """
        Search tasks by title or description.

        Args:
            query: Search query

        Returns:
            List of matching tasks
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM tasks
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY ai_score DESC
            """, (f"%{query}%", f"%{query}%"))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []


if __name__ == "__main__":
    # Test the TodoManager
    manager = TodoManager()

    # Add sample tasks
    task_id = manager.add_task(
        title="Process Penterra Documents",
        description="Review and OCR scan all pending Penterra PDFs",
        project="Penterra",
        priority="High",
        tags=["ocr", "urgent"]
    )
    print(f"Created task: {task_id}")

    # Get next best move
    next_task = manager.get_next_best_move()
    if next_task:
        print(f"Next best move: {next_task['title']}")

    # Get statistics
    stats = manager.get_statistics()
    print(f"Statistics: {stats}")
