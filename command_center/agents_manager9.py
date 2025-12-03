"""
DataBossX Agents Manager
Manages AI agents with different roles and capabilities.
Handles task queuing and agent assignment.
"""

import json
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Agent:
    """
    Represents an AI agent with specific role and capabilities.
    """

    def __init__(self, agent_id: str, name: str, role: str, description: str,
                 icon: str = "🤖", capabilities: Optional[List[str]] = None,
                 specialties: Optional[List[str]] = None, active: bool = True):
        """
        Initialize an Agent.

        Args:
            agent_id: Unique identifier
            name: Agent display name
            role: Primary role
            description: What the agent does
            icon: Emoji icon
            capabilities: List of capabilities
            specialties: Areas of expertise
            active: Whether agent is currently active
        """
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.description = description
        self.icon = icon
        self.capabilities = capabilities or []
        self.specialties = specialties or []
        self.active = active

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'role': self.role,
            'description': self.description,
            'icon': self.icon,
            'capabilities': self.capabilities,
            'specialties': self.specialties,
            'active': self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create Agent from dictionary."""
        return cls(**data)


class AgentTask:
    """
    Represents a task assigned to an agent.
    """

    def __init__(self, task_id: Optional[int] = None, agent_id: str = "",
                 title: str = "", description: str = "", priority: str = "Medium",
                 status: str = "Queued", created_at: Optional[str] = None,
                 started_at: Optional[str] = None, completed_at: Optional[str] = None,
                 result: Optional[str] = None, error: Optional[str] = None):
        """
        Initialize an AgentTask.

        Args:
            task_id: Unique task identifier
            agent_id: ID of assigned agent
            title: Task title
            description: Detailed task description
            priority: Priority level
            status: Current status (Queued, Running, Completed, Failed)
            created_at: Creation timestamp
            started_at: Start timestamp
            completed_at: Completion timestamp
            result: Task result
            error: Error message if failed
        """
        self.task_id = task_id
        self.agent_id = agent_id
        self.title = title
        self.description = description
        self.priority = priority
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.started_at = started_at
        self.completed_at = completed_at
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            'task_id': self.task_id,
            'agent_id': self.agent_id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'result': self.result,
            'error': self.error,
        }


class AgentsManager:
    """
    Manages AI agents and their tasks.
    """

    def __init__(self, config_file: str = "agents_config9.json",
                 db_path: str = "databossx_agents.db"):
        """
        Initialize the AgentsManager.

        Args:
            config_file: Path to agents configuration file
            db_path: Path to SQLite database for agent tasks
        """
        self.config_file = config_file
        self.db_path = db_path
        self.agents: Dict[str, Agent] = {}
        self._init_database()
        self._load_or_create_config()

    def _init_database(self) -> None:
        """
        Initialize the database schema for agent tasks.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create agent_tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_tasks (
                        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        priority TEXT DEFAULT 'Medium',
                        status TEXT DEFAULT 'Queued',
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        result TEXT,
                        error TEXT
                    )
                """)

                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_agent_id ON agent_tasks(agent_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON agent_tasks(status)
                """)

                conn.commit()
                logger.info(f"Agent tasks database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing agent database: {e}")
            raise

    def _get_default_agents(self) -> List[Dict[str, Any]]:
        """
        Get default agent configurations.

        Returns:
            List of default agent dictionaries
        """
        return [
            {
                "agent_id": "builder",
                "name": "Builder",
                "role": "Software Engineer",
                "description": "Writes code, creates features, and builds applications",
                "icon": "👷",
                "capabilities": ["coding", "debugging", "architecture", "testing"],
                "specialties": ["Python", "JavaScript", "API Development", "Database Design"],
                "active": True
            },
            {
                "agent_id": "researcher",
                "name": "Researcher",
                "role": "Research Specialist",
                "description": "Conducts deep research, gathers information, and analyzes data",
                "icon": "🔬",
                "capabilities": ["research", "analysis", "data-gathering", "summarization"],
                "specialties": ["Web Research", "Document Analysis", "Genealogy", "Public Records"],
                "active": True
            },
            {
                "agent_id": "tester",
                "name": "Tester",
                "role": "QA Engineer",
                "description": "Tests software, finds bugs, and ensures quality",
                "icon": "🧪",
                "capabilities": ["testing", "qa", "debugging", "validation"],
                "specialties": ["Unit Testing", "Integration Testing", "Bug Reports", "Test Automation"],
                "active": True
            },
            {
                "agent_id": "money_maker",
                "name": "Money Maker",
                "role": "Business Development",
                "description": "Identifies opportunities, analyzes deals, and generates revenue strategies",
                "icon": "💰",
                "capabilities": ["deal-analysis", "opportunity-identification", "roi-calculation", "strategy"],
                "specialties": ["Missing Owner Cases", "Mineral Rights", "Real Estate", "Business Analysis"],
                "active": True
            },
            {
                "agent_id": "title_ocr",
                "name": "Title OCR Agent",
                "role": "Document Processing",
                "description": "Processes title documents, extracts data, and structures information",
                "icon": "📄",
                "capabilities": ["ocr", "document-parsing", "data-extraction", "validation"],
                "specialties": ["Title Abstracts", "Legal Descriptions", "Lease Documents", "County Records"],
                "active": True
            },
            {
                "agent_id": "deal_finder",
                "name": "Deal Finder",
                "role": "Opportunity Scout",
                "description": "Scouts for deals, finds prospects, and identifies high-value opportunities",
                "icon": "🎯",
                "capabilities": ["prospecting", "deal-scoring", "market-analysis", "lead-generation"],
                "specialties": ["Mineral Rights", "Property Deals", "Missing Owners", "Market Research"],
                "active": True
            },
            {
                "agent_id": "artist",
                "name": "Artist",
                "role": "Creative Designer",
                "description": "Creates designs, generates visualizations, and produces creative content",
                "icon": "🎨",
                "capabilities": ["design", "visualization", "ui-ux", "content-creation"],
                "specialties": ["UI Design", "Data Visualization", "Graphics", "Branding"],
                "active": True
            },
        ]

    def _load_or_create_config(self) -> None:
        """
        Load configuration from file or create default.
        """
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Load agents
                for agent_data in config.get('agents', []):
                    agent = Agent.from_dict(agent_data)
                    self.agents[agent.agent_id] = agent

                logger.info(f"Agents configuration loaded: {len(self.agents)} agents")

            else:
                logger.info("Creating default agents configuration")
                # Create default agents
                for agent_data in self._get_default_agents():
                    agent = Agent(**agent_data)
                    self.agents[agent.agent_id] = agent

                self.save_config()

        except Exception as e:
            logger.error(f"Error loading agents configuration: {e}")
            raise

    def save_config(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if successful
        """
        try:
            config = {
                'agents': [agent.to_dict() for agent in self.agents.values()],
                'last_updated': datetime.now().isoformat()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Agents configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving agents configuration: {e}")
            return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_all_agents(self, active_only: bool = False) -> List[Agent]:
        """
        Get all agents.

        Args:
            active_only: Only return active agents

        Returns:
            List of agents
        """
        agents = list(self.agents.values())
        if active_only:
            agents = [a for a in agents if a.active]
        return agents

    def queue_task(self, agent_id: str, title: str, description: str,
                   priority: str = "Medium") -> int:
        """
        Queue a task for an agent.

        Args:
            agent_id: ID of agent to assign task to
            title: Task title
            description: Task description
            priority: Priority level

        Returns:
            Task ID
        """
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent not found: {agent_id}")

            task = AgentTask(
                agent_id=agent_id,
                title=title,
                description=description,
                priority=priority,
                status="Queued"
            )

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO agent_tasks (agent_id, title, description, priority,
                                           status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task.agent_id,
                    task.title,
                    task.description,
                    task.priority,
                    task.status,
                    task.created_at
                ))

                task_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Task queued for {agent_id}: {task_id} - {title}")
                return task_id

        except Exception as e:
            logger.error(f"Error queuing task: {e}")
            raise

    def get_task(self, task_id: int) -> Optional[AgentTask]:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            AgentTask or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,))
                row = cursor.fetchone()

                if row:
                    return AgentTask(**dict(row))
                return None

        except Exception as e:
            logger.error(f"Error retrieving task: {e}")
            return None

    def get_agent_tasks(self, agent_id: Optional[str] = None,
                       status: Optional[str] = None,
                       limit: Optional[int] = None) -> List[AgentTask]:
        """
        Get tasks with optional filtering.

        Args:
            agent_id: Filter by agent
            status: Filter by status
            limit: Maximum number of tasks

        Returns:
            List of AgentTasks
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT * FROM agent_tasks WHERE 1=1"
                params = []

                if agent_id:
                    query += " AND agent_id = ?"
                    params.append(agent_id)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY created_at DESC"

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [AgentTask(**dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Error retrieving tasks: {e}")
            return []

    def update_task_status(self, task_id: int, status: str,
                          result: Optional[str] = None,
                          error: Optional[str] = None) -> bool:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status
            result: Task result (if completed)
            error: Error message (if failed)

        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                updates = ["status = ?"]
                params = [status]

                if status == "Running":
                    updates.append("started_at = ?")
                    params.append(datetime.now().isoformat())

                if status in ["Completed", "Failed"]:
                    updates.append("completed_at = ?")
                    params.append(datetime.now().isoformat())

                if result:
                    updates.append("result = ?")
                    params.append(result)

                if error:
                    updates.append("error = ?")
                    params.append(error)

                params.append(task_id)

                query = f"UPDATE agent_tasks SET {', '.join(updates)} WHERE task_id = ?"
                cursor.execute(query, params)

                conn.commit()
                logger.info(f"Task {task_id} status updated to {status}")
                return True

        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return False

    def execute_task(self, task_id: int, use_llm: bool = True) -> Dict[str, Any]:
        """
        Execute a queued task (placeholder for actual execution).

        Args:
            task_id: Task ID to execute
            use_llm: Whether to use LLM for execution

        Returns:
            Dictionary with execution result
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        agent = self.get_agent(task.agent_id)
        if not agent:
            return {"success": False, "error": "Agent not found"}

        try:
            # Update status to Running
            self.update_task_status(task_id, "Running")

            # Placeholder for actual LLM execution
            # In production, this would call llm_router or similar
            result = f"Task '{task.title}' processed by {agent.name}\n\n"
            result += f"Agent Role: {agent.role}\n"
            result += f"Task Description: {task.description}\n\n"

            if use_llm:
                result += "[Note: LLM integration would execute the actual task here]\n"
                result += f"Agent capabilities: {', '.join(agent.capabilities)}\n"
                result += f"Agent specialties: {', '.join(agent.specialties)}"
            else:
                result += "[Task execution simulated - LLM disabled]"

            # Update status to Completed
            self.update_task_status(task_id, "Completed", result=result)

            logger.info(f"Task {task_id} executed successfully")
            return {"success": True, "result": result}

        except Exception as e:
            error_msg = str(e)
            self.update_task_status(task_id, "Failed", error=error_msg)
            logger.error(f"Error executing task {task_id}: {e}")
            return {"success": False, "error": error_msg}

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get agent statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                stats = {}

                # Total tasks
                cursor.execute("SELECT COUNT(*) FROM agent_tasks")
                stats['total_tasks'] = cursor.fetchone()[0]

                # By status
                cursor.execute("SELECT status, COUNT(*) FROM agent_tasks GROUP BY status")
                stats['by_status'] = dict(cursor.fetchall())

                # By agent
                cursor.execute("SELECT agent_id, COUNT(*) FROM agent_tasks GROUP BY agent_id")
                stats['by_agent'] = dict(cursor.fetchall())

                # Active agents
                stats['active_agents'] = len([a for a in self.agents.values() if a.active])

                return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test the AgentsManager
    print("Testing AgentsManager...")

    manager = AgentsManager()

    print(f"\nTotal agents: {len(manager.agents)}")

    # Show all agents
    print("\nAvailable Agents:")
    for agent in manager.get_all_agents():
        print(f"  {agent.icon} {agent.name} ({agent.role})")
        print(f"     {agent.description}")
        print(f"     Capabilities: {', '.join(agent.capabilities)}")

    # Queue a sample task
    task_id = manager.queue_task(
        agent_id="builder",
        title="Create data export feature",
        description="Build a feature to export task data to CSV",
        priority="High"
    )
    print(f"\nQueued task {task_id} for Builder agent")

    # Show statistics
    stats = manager.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
