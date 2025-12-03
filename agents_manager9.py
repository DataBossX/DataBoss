"""
DataBossX Agents Manager v9
AI Agent orchestration system with specialized roles and task queuing
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

from config_databossx9 import get_config

# Configure logging
logger = logging.getLogger(__name__)


class AgentsManager:
    """
    Manages AI agents with specialized roles and task queuing.
    Integrates with LLM router for task processing.
    """

    def __init__(self, agents_config_file: str = "config/agents_config9.json",
                 db_path: Optional[str] = None):
        """
        Initialize Agents Manager.

        Args:
            agents_config_file: Path to agents configuration file
            db_path: Path to SQLite database
        """
        config = get_config()
        self.agents_config_file = Path(agents_config_file)
        self.db_path = db_path or config.get('paths', 'database_path', 'databossx.db')
        self.agents: Dict[str, Any] = {}
        self._ensure_config_directory()
        self.load_agents()
        self._init_database()
        logger.info("AgentsManager initialized")

    def _ensure_config_directory(self):
        """Ensure configuration directory exists"""
        self.agents_config_file.parent.mkdir(parents=True, exist_ok=True)

    def load_agents(self):
        """Load agents configuration"""
        try:
            if self.agents_config_file.exists():
                with open(self.agents_config_file, 'r') as f:
                    data = json.load(f)
                    self.agents = data.get('agents', {})
                logger.info(f"Agents loaded from {self.agents_config_file}")
            else:
                self._create_default_agents()
                logger.info("Default agents configuration created")
        except Exception as e:
            logger.error(f"Error loading agents: {e}")
            self._create_default_agents()

    def _create_default_agents(self):
        """Create default agent configurations"""
        self.agents = {
            "builder": {
                "name": "Builder",
                "role": "Code Development",
                "description": "Expert in Python, SQL, and system architecture. Builds and maintains code.",
                "icon": "👷",
                "specialties": ["Python", "SQL", "FastAPI", "Streamlit", "Database Design"],
                "system_prompt": "You are the Builder agent. You excel at writing clean, production-ready code with proper error handling and documentation.",
                "active": True,
                "max_concurrent_tasks": 3
            },
            "researcher": {
                "name": "Researcher",
                "role": "Information Gathering",
                "description": "Specialist in research, data gathering, and analysis. Finds information efficiently.",
                "icon": "🔬",
                "specialties": ["Web Research", "Data Analysis", "Genealogy", "Title Research"],
                "system_prompt": "You are the Researcher agent. You excel at finding, analyzing, and synthesizing information from multiple sources.",
                "active": True,
                "max_concurrent_tasks": 5
            },
            "tester": {
                "name": "Tester",
                "role": "Quality Assurance",
                "description": "Tests code, identifies bugs, and ensures quality. Creates test cases.",
                "icon": "🧪",
                "specialties": ["Testing", "Debugging", "QA", "Test Automation"],
                "system_prompt": "You are the Tester agent. You excel at finding bugs, edge cases, and ensuring code quality.",
                "active": True,
                "max_concurrent_tasks": 2
            },
            "money_maker": {
                "name": "Money Maker",
                "role": "Business Development",
                "description": "Identifies opportunities, analyzes deals, and generates revenue strategies.",
                "icon": "💰",
                "specialties": ["Deal Analysis", "Missing Owners", "Mineral Rights", "Real Estate"],
                "system_prompt": "You are the Money Maker agent. You excel at identifying profitable opportunities and creating actionable business strategies.",
                "active": True,
                "max_concurrent_tasks": 3
            },
            "title_ocr_agent": {
                "name": "Title OCR Agent",
                "role": "Document Processing",
                "description": "Specializes in OCR, document parsing, and title abstract extraction.",
                "icon": "📄",
                "specialties": ["OCR", "Document Parsing", "Title Abstracts", "Data Extraction"],
                "system_prompt": "You are the Title OCR Agent. You excel at processing documents, extracting structured data, and ensuring accuracy.",
                "active": True,
                "max_concurrent_tasks": 4
            },
            "deal_finder": {
                "name": "Deal Finder",
                "role": "Opportunity Discovery",
                "description": "Hunts for deals, missing owners, and lucrative opportunities.",
                "icon": "🎯",
                "specialties": ["Deal Sourcing", "Missing Owner Research", "Property Analysis"],
                "system_prompt": "You are the Deal Finder agent. You excel at discovering hidden opportunities and assessing their potential value.",
                "active": True,
                "max_concurrent_tasks": 3
            },
            "artist": {
                "name": "Artist",
                "role": "Creative & Design",
                "description": "Handles UI/UX design, graphics, and creative tasks.",
                "icon": "🎨",
                "specialties": ["UI Design", "Graphics", "Branding", "Visual Design"],
                "system_prompt": "You are the Artist agent. You excel at creating beautiful, user-friendly interfaces and visual assets.",
                "active": True,
                "max_concurrent_tasks": 2
            }
        }
        self.save_agents()

    def save_agents(self):
        """Save agents configuration"""
        try:
            data = {
                "agents": self.agents,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.agents_config_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Agents configuration saved")
        except Exception as e:
            logger.error(f"Error saving agents: {e}")

    def _init_database(self):
        """Initialize agent tasks database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Agent tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    task_title TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    task_type TEXT,
                    priority TEXT DEFAULT 'Medium',
                    status TEXT DEFAULT 'queued',
                    requested_by TEXT DEFAULT 'user',
                    requested_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    model_used TEXT,
                    tokens_used INTEGER,
                    processing_time REAL
                )
            """)

            # Agent performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    metric_date TEXT NOT NULL,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0,
                    avg_processing_time REAL DEFAULT 0.0,
                    total_tokens_used INTEGER DEFAULT 0
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent ON agent_tasks(agent_id)")

            conn.commit()
            conn.close()
            logger.info("Agent database initialized")

        except Exception as e:
            logger.error(f"Error initializing agent database: {e}")
            raise

    def get_all_agents(self) -> Dict[str, Any]:
        """Get all agent configurations"""
        return self.agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific agent configuration.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent configuration or None
        """
        return self.agents.get(agent_id)

    def queue_task(self, agent_id: str, task_title: str, task_description: str,
                   task_type: str = "general", priority: str = "Medium") -> Optional[int]:
        """
        Queue a task for an agent.

        Args:
            agent_id: Agent identifier
            task_title: Task title
            task_description: Task description
            task_type: Type of task
            priority: Priority level

        Returns:
            Task ID or None
        """
        try:
            if agent_id not in self.agents:
                logger.warning(f"Agent not found: {agent_id}")
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO agent_tasks
                (agent_id, task_title, task_description, task_type, priority, status, requested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, task_title, task_description, task_type, priority,
                  'queued', datetime.now().isoformat()))

            task_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Task queued for {agent_id}: {task_title}")
            return task_id

        except Exception as e:
            logger.error(f"Error queuing task: {e}")
            return None

    def process_task(self, task_id: int) -> bool:
        """
        Process a queued task using LLM.

        Args:
            task_id: Task ID

        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get task details
            cursor.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,))
            task = cursor.fetchone()

            if not task:
                logger.warning(f"Task not found: {task_id}")
                return False

            # Update status to processing
            cursor.execute("""
                UPDATE agent_tasks
                SET status = ?, started_at = ?
                WHERE id = ?
            """, ('processing', datetime.now().isoformat(), task_id))
            conn.commit()

            # Get agent config
            agent_id = task[1]
            agent = self.agents.get(agent_id)

            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")

            # Prepare prompt
            system_prompt = agent.get('system_prompt', '')
            task_description = task[3]
            full_prompt = f"{system_prompt}\n\nTask: {task_description}"

            # Process with LLM (mock implementation - integrate with actual LLM router)
            result = self._call_llm(full_prompt, agent_id)

            # Update task with result
            cursor.execute("""
                UPDATE agent_tasks
                SET status = ?, completed_at = ?, result = ?
                WHERE id = ?
            """, ('completed', datetime.now().isoformat(), result, task_id))

            conn.commit()
            conn.close()

            logger.info(f"Task completed: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")

            # Update task with error
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE agent_tasks
                    SET status = ?, error = ?
                    WHERE id = ?
                """, ('failed', str(e), task_id))
                conn.commit()
                conn.close()
            except:
                pass

            return False

    def _call_llm(self, prompt: str, agent_id: str) -> str:
        """
        Call LLM router (mock implementation).

        Args:
            prompt: Input prompt
            agent_id: Agent identifier

        Returns:
            LLM response
        """
        # This is a mock implementation
        # In production, this would integrate with the actual LLM router
        # from the existing backend/server.py

        try:
            # Try to import and use existing LLM clients if available
            from dotenv import load_dotenv
            load_dotenv()

            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")

            # Prefer Claude for most tasks, fallback to GPT
            if anthropic_key:
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    response = client.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text
                except Exception as e:
                    logger.warning(f"Claude API failed: {e}")

            if openai_key:
                try:
                    import openai
                    client = openai.OpenAI(api_key=openai_key)
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=2000
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    logger.warning(f"OpenAI API failed: {e}")

            # Fallback to mock response
            return f"[Mock Response] Task processed by {agent_id} agent.\n\nPrompt: {prompt[:100]}...\n\nThis is a mock response. Configure API keys to enable real LLM processing."

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"Error processing task: {str(e)}"

    def get_agent_tasks(self, agent_id: str, status: Optional[str] = None,
                       limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get tasks for specific agent.

        Args:
            agent_id: Agent identifier
            status: Filter by status
            limit: Maximum number of tasks

        Returns:
            List of task dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM agent_tasks WHERE agent_id = ?"
            params = [agent_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY requested_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting agent tasks: {e}")
            return []

    def get_all_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all tasks across all agents.

        Args:
            status: Filter by status
            limit: Maximum number of tasks

        Returns:
            List of task dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM agent_tasks WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY requested_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting all tasks: {e}")
            return []

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get performance statistics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Statistics dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Total tasks
            cursor.execute("SELECT COUNT(*) FROM agent_tasks WHERE agent_id = ?", (agent_id,))
            stats['total_tasks'] = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM agent_tasks
                WHERE agent_id = ?
                GROUP BY status
            """, (agent_id,))
            stats['by_status'] = dict(cursor.fetchall())

            # Success rate
            completed = stats['by_status'].get('completed', 0)
            failed = stats['by_status'].get('failed', 0)
            total_finished = completed + failed
            stats['success_rate'] = (completed / total_finished * 100) if total_finished > 0 else 0

            # Average processing time
            cursor.execute("""
                SELECT AVG(processing_time)
                FROM agent_tasks
                WHERE agent_id = ? AND processing_time IS NOT NULL
            """, (agent_id,))
            avg_time = cursor.fetchone()[0]
            stats['avg_processing_time'] = avg_time if avg_time else 0

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting agent stats: {e}")
            return {}


if __name__ == "__main__":
    # Test the AgentsManager
    manager = AgentsManager()

    print(f"Total agents: {len(manager.get_all_agents())}")
    print("Agents:")
    for agent_id, agent in manager.get_all_agents().items():
        print(f"  - {agent['name']} ({agent['role']})")

    # Queue a test task
    task_id = manager.queue_task(
        "builder",
        "Create a new module",
        "Build a module for handling data exports in CSV and JSON formats"
    )
    print(f"\nQueued task: {task_id}")
