"""
DataBossX To-Do Manager
Manages tasks with SQLite database, AI-powered prioritization, and filtering.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class Task:
    """
    Represents a single task in the system.
    """

    def __init__(self, task_id: Optional[int] = None, title: str = "", description: str = "",
                 project: str = "System", priority: str = "Medium", status: str = "Todo",
                 due_date: Optional[str] = None, created_at: Optional[str] = None,
                 completed_at: Optional[str] = None, tags: Optional[str] = None,
                 ai_score: int = 50, assigned_to: Optional[str] = None):
        """
        Initialize a Task object.

        Args:
            task_id: Unique task identifier
            title: Task title
            description: Detailed description
            project: Project category (Penterra, Genealogy, System)
            priority: Priority level (Low, Medium, High, Critical)
            status: Current status (Todo, In Progress, Blocked, Done)
            due_date: ISO format date string
            created_at: ISO format datetime string
            completed_at: ISO format datetime string
            tags: Comma-separated tags
            ai_score: AI-calculated priority score (0-100)
            assigned_to: Person or agent assigned
        """
        self.task_id = task_id
        self.title = title
        self.description = description
        self.project = project
        self.priority = priority
        self.status = status
        self.due_date = due_date
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at
        self.tags = tags
        self.ai_score = ai_score
        self.assigned_to = assigned_to

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            'task_id': self.task_id,
            'title': self.title,
            'description': self.description,
            'project': self.project,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'tags': self.tags,
            'ai_score': self.ai_score,
            'assigned_to': self.assigned_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create Task from dictionary."""
        return cls(**data)


class TodoManager:
    """
    Manages the task database and provides task operations.
    """

    def __init__(self, db_path: str = "databossx_tasks.db"):
        """
        Initialize the TodoManager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """
        Initialize the database schema.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        project TEXT DEFAULT 'System',
                        priority TEXT DEFAULT 'Medium',
                        status TEXT DEFAULT 'Todo',
                        due_date TEXT,
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        tags TEXT,
                        ai_score INTEGER DEFAULT 50,
                        assigned_to TEXT
                    )
                """)

                # Create indexes for common queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_project ON tasks(project)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ai_score ON tasks(ai_score DESC)
                """)

                conn.commit()
                logger.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def add_task(self, task: Task) -> int:
        """
        Add a new task to the database.

        Args:
            task: Task object to add

        Returns:
            ID of the created task
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO tasks (title, description, project, priority, status,
                                     due_date, created_at, tags, ai_score, assigned_to)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.title,
                    task.description,
                    task.project,
                    task.priority,
                    task.status,
                    task.due_date,
                    task.created_at,
                    task.tags,
                    task.ai_score,
                    task.assigned_to
                ))

                task_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Task added: {task_id} - {task.title}")
                return task_id

        except Exception as e:
            logger.error(f"Error adding task: {e}")
            raise

    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Retrieve a task by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                row = cursor.fetchone()

                if row:
                    return Task(**dict(row))
                return None

        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            return None

    def update_task(self, task: Task) -> bool:
        """
        Update an existing task.

        Args:
            task: Task object with updated values

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tasks
                    SET title = ?, description = ?, project = ?, priority = ?,
                        status = ?, due_date = ?, completed_at = ?, tags = ?,
                        ai_score = ?, assigned_to = ?
                    WHERE task_id = ?
                """, (
                    task.title,
                    task.description,
                    task.project,
                    task.priority,
                    task.status,
                    task.due_date,
                    task.completed_at,
                    task.tags,
                    task.ai_score,
                    task.assigned_to,
                    task.task_id
                ))

                conn.commit()
                logger.info(f"Task updated: {task.task_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return False

    def delete_task(self, task_id: int) -> bool:
        """
        Delete a task.

        Args:
            task_id: ID of task to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                logger.info(f"Task deleted: {task_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            return False

    def get_tasks(self, project: Optional[str] = None, priority: Optional[str] = None,
                  status: Optional[str] = None, limit: Optional[int] = None) -> List[Task]:
        """
        Retrieve tasks with optional filtering.

        Args:
            project: Filter by project
            priority: Filter by priority
            status: Filter by status
            limit: Maximum number of tasks to return

        Returns:
            List of Task objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT * FROM tasks WHERE 1=1"
                params = []

                if project:
                    query += " AND project = ?"
                    params.append(project)

                if priority:
                    query += " AND priority = ?"
                    params.append(priority)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY ai_score DESC, created_at DESC"

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [Task(**dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Error retrieving tasks: {e}")
            return []

    def get_next_best_move(self, use_ai: bool = True) -> Optional[Task]:
        """
        Get the highest priority task using AI scoring or heuristics.

        Args:
            use_ai: Whether to attempt AI-based scoring

        Returns:
            The most important task to work on next
        """
        try:
            # Get all incomplete tasks
            tasks = self.get_tasks(status="Todo") + self.get_tasks(status="In Progress")

            if not tasks:
                return None

            # Calculate scores for all tasks
            for task in tasks:
                task.ai_score = self._calculate_task_score(task, use_ai)

            # Sort by AI score
            tasks.sort(key=lambda t: t.ai_score, reverse=True)

            # Update scores in database
            for task in tasks[:5]:  # Update top 5
                self.update_task(task)

            return tasks[0] if tasks else None

        except Exception as e:
            logger.error(f"Error calculating next best move: {e}")
            return None

    def _calculate_task_score(self, task: Task, use_ai: bool = True) -> int:
        """
        Calculate priority score for a task.

        Args:
            task: Task to score
            use_ai: Whether to use AI (future enhancement)

        Returns:
            Score from 0-100
        """
        score = 50  # Base score

        # Priority weight
        priority_scores = {
            'Critical': 40,
            'High': 30,
            'Medium': 20,
            'Low': 10
        }
        score += priority_scores.get(task.priority, 20)

        # Status weight (In Progress tasks are more important)
        if task.status == "In Progress":
            score += 20
        elif task.status == "Blocked":
            score -= 20

        # Due date weight
        if task.due_date:
            try:
                due = datetime.fromisoformat(task.due_date)
                now = datetime.now()
                days_until_due = (due - now).days

                if days_until_due < 0:
                    score += 30  # Overdue
                elif days_until_due < 3:
                    score += 25  # Due soon
                elif days_until_due < 7:
                    score += 15  # Due this week
            except:
                pass

        # Project weight (Money-related projects get boost)
        if task.project == "Penterra":
            score += 10
        elif "deal" in task.title.lower() or "money" in task.title.lower():
            score += 15

        # Keep score in 0-100 range
        return max(0, min(100, score))

    def mark_complete(self, task_id: int) -> bool:
        """
        Mark a task as complete.

        Args:
            task_id: ID of task to complete

        Returns:
            True if successful
        """
        task = self.get_task(task_id)
        if task:
            task.status = "Done"
            task.completed_at = datetime.now().isoformat()
            return self.update_task(task)
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get task statistics.

        Returns:
            Dictionary with various statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
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

                # Completed this week
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE status = 'Done' AND completed_at > ?
                """, (week_ago,))
                stats['completed_this_week'] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def search_tasks(self, query: str) -> List[Task]:
        """
        Search tasks by title or description.

        Args:
            query: Search query

        Returns:
            List of matching tasks
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM tasks
                    WHERE title LIKE ? OR description LIKE ?
                    ORDER BY ai_score DESC
                """, (f'%{query}%', f'%{query}%'))

                rows = cursor.fetchall()
                return [Task(**dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []


# Convenience functions for quick operations
def quick_add_task(title: str, project: str = "System", priority: str = "Medium",
                   description: str = "") -> int:
    """
    Quickly add a task with minimal parameters.

    Args:
        title: Task title
        project: Project category
        priority: Priority level
        description: Task description

    Returns:
        Task ID
    """
    manager = TodoManager()
    task = Task(title=title, project=project, priority=priority, description=description)
    return manager.add_task(task)


def get_todays_tasks() -> List[Task]:
    """
    Get all tasks for today.

    Returns:
        List of tasks
    """
    manager = TodoManager()
    today = datetime.now().date().isoformat()

    all_tasks = manager.get_tasks()
    todays_tasks = []

    for task in all_tasks:
        if task.due_date and task.due_date.startswith(today):
            todays_tasks.append(task)
        elif task.status == "In Progress":
            todays_tasks.append(task)

    return todays_tasks


if __name__ == "__main__":
    # Test the TodoManager
    print("Testing TodoManager...")

    manager = TodoManager()

    # Add sample tasks
    sample_tasks = [
        Task(title="Process Penterra PDFs", project="Penterra", priority="High",
             description="Run OCR on pending documents"),
        Task(title="Update genealogy records", project="Genealogy", priority="Medium",
             description="Import new FamilySearch data"),
        Task(title="System maintenance", project="System", priority="Low",
             description="Update dependencies"),
    ]

    for task in sample_tasks:
        task_id = manager.add_task(task)
        print(f"Added task {task_id}: {task.title}")

    # Get next best move
    next_task = manager.get_next_best_move()
    if next_task:
        print(f"\nNext Best Move: {next_task.title} (Score: {next_task.ai_score})")

    # Show statistics
    stats = manager.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
