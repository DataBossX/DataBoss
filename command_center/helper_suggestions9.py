"""
DataBossX Helper Suggestions System
Provides contextual tips, warnings, and helpful suggestions.
Scans the system for actionable items and surfaces them to the user.
"""

import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class Suggestion:
    """
    Represents a helpful suggestion or tip.
    """

    def __init__(self, suggestion_id: str, title: str, message: str,
                 level: str = "info", action_text: Optional[str] = None,
                 action_callback: Optional[str] = None, dismissable: bool = True):
        """
        Initialize a Suggestion.

        Args:
            suggestion_id: Unique identifier
            title: Suggestion title
            message: Suggestion message
            level: Level (info, tip, warning, critical)
            action_text: Text for action button
            action_callback: Callback identifier for action
            dismissable: Whether user can dismiss this
        """
        self.suggestion_id = suggestion_id
        self.title = title
        self.message = message
        self.level = level
        self.action_text = action_text
        self.action_callback = action_callback
        self.dismissable = dismissable
        self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'suggestion_id': self.suggestion_id,
            'title': self.title,
            'message': self.message,
            'level': self.level,
            'action_text': self.action_text,
            'action_callback': self.action_callback,
            'dismissable': self.dismissable,
            'created_at': self.created_at.isoformat(),
        }


class HelperSuggestions:
    """
    Generates and manages helpful suggestions for the user.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the helper suggestions system.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.dismissed_suggestions: List[str] = []

    def scan_for_suggestions(self) -> List[Suggestion]:
        """
        Scan the system for actionable items and generate suggestions.

        Returns:
            List of Suggestion objects
        """
        suggestions = []

        try:
            # Check for unprocessed PDFs
            pdf_suggestion = self._check_unprocessed_pdfs()
            if pdf_suggestion:
                suggestions.append(pdf_suggestion)

            # Check for high-value deals
            deals_suggestion = self._check_high_value_deals()
            if deals_suggestion:
                suggestions.append(deals_suggestion)

            # Check for pending tasks
            tasks_suggestion = self._check_pending_tasks()
            if tasks_suggestion:
                suggestions.append(tasks_suggestion)

            # Check for agent queue
            agents_suggestion = self._check_agent_queue()
            if agents_suggestion:
                suggestions.append(agents_suggestion)

            # Check for system updates
            system_suggestion = self._check_system_status()
            if system_suggestion:
                suggestions.append(system_suggestion)

            # Add motivational tip
            if not suggestions:
                suggestions.append(self._get_motivational_tip())

        except Exception as e:
            logger.error(f"Error scanning for suggestions: {e}")

        return [s for s in suggestions if s.suggestion_id not in self.dismissed_suggestions]

    def _check_unprocessed_pdfs(self) -> Optional[Suggestion]:
        """
        Check for unprocessed PDF files.

        Returns:
            Suggestion if PDFs found, None otherwise
        """
        try:
            input_dirs = self.config.get('input_dirs', ['input', 'penterra_files'])
            pdf_count = 0

            for input_dir in input_dirs:
                if os.path.exists(input_dir):
                    for root, _, files in os.walk(input_dir):
                        pdf_count += sum(1 for f in files if f.lower().endswith('.pdf'))

            if pdf_count > 0:
                return Suggestion(
                    suggestion_id="unprocessed_pdfs",
                    title="Unprocessed Documents",
                    message=f"You have {pdf_count} unprocessed PDF document(s) in your input folders.",
                    level="tip",
                    action_text="Process Documents",
                    action_callback="process_pdfs"
                )

        except Exception as e:
            logger.error(f"Error checking PDFs: {e}")

        return None

    def _check_high_value_deals(self) -> Optional[Suggestion]:
        """
        Check for high-value deals in the pipeline.

        Returns:
            Suggestion if high-value deals found
        """
        try:
            # Import here to avoid circular dependency
            from command_center.deals_engine9 import DealsEngine

            engine = DealsEngine()
            high_value_deals = engine.get_deals(status="Prospect", min_score=70, limit=5)

            if high_value_deals:
                total_value = sum(d.estimated_value for d in high_value_deals)

                return Suggestion(
                    suggestion_id="high_value_deals",
                    title="High-Value Opportunities",
                    message=f"You have {len(high_value_deals)} high-scoring deals worth an estimated ${total_value:,.2f}. Consider reviewing them!",
                    level="warning",
                    action_text="View Deals",
                    action_callback="view_deals"
                )

        except Exception as e:
            logger.error(f"Error checking deals: {e}")

        return None

    def _check_pending_tasks(self) -> Optional[Suggestion]:
        """
        Check for pending high-priority tasks.

        Returns:
            Suggestion if critical tasks found
        """
        try:
            # Import here to avoid circular dependency
            from command_center.todo_manager9 import TodoManager

            manager = TodoManager()
            high_priority = manager.get_tasks(priority="High", status="Todo", limit=10)
            critical = manager.get_tasks(priority="Critical", status="Todo", limit=5)

            if critical:
                return Suggestion(
                    suggestion_id="critical_tasks",
                    title="Critical Tasks",
                    message=f"You have {len(critical)} critical task(s) that need immediate attention!",
                    level="critical",
                    action_text="View Tasks",
                    action_callback="view_tasks",
                    dismissable=False
                )
            elif len(high_priority) >= 5:
                return Suggestion(
                    suggestion_id="high_priority_tasks",
                    title="High Priority Tasks",
                    message=f"You have {len(high_priority)} high-priority tasks pending.",
                    level="warning",
                    action_text="View Tasks",
                    action_callback="view_tasks"
                )

        except Exception as e:
            logger.error(f"Error checking tasks: {e}")

        return None

    def _check_agent_queue(self) -> Optional[Suggestion]:
        """
        Check for queued agent tasks.

        Returns:
            Suggestion if queued tasks found
        """
        try:
            # Import here to avoid circular dependency
            from command_center.agents_manager9 import AgentsManager

            manager = AgentsManager()
            queued = manager.get_agent_tasks(status="Queued", limit=10)

            if len(queued) >= 3:
                return Suggestion(
                    suggestion_id="queued_agent_tasks",
                    title="Agent Tasks Queued",
                    message=f"You have {len(queued)} task(s) queued for AI agents. Consider processing them!",
                    level="info",
                    action_text="View Agent Tasks",
                    action_callback="view_agents"
                )

        except Exception as e:
            logger.error(f"Error checking agent queue: {e}")

        return None

    def _check_system_status(self) -> Optional[Suggestion]:
        """
        Check system status and configuration.

        Returns:
            Suggestion if issues found
        """
        try:
            issues = []

            # Check if directories exist
            required_dirs = ['input', 'output', 'assets']
            for dir_name in required_dirs:
                if not os.path.exists(dir_name):
                    issues.append(f"Missing directory: {dir_name}")

            # Check if logo exists
            if not os.path.exists('assets/databossx_logo.png'):
                issues.append("Logo not generated yet")

            if issues:
                return Suggestion(
                    suggestion_id="system_issues",
                    title="System Setup",
                    message=f"Some system components need attention: {', '.join(issues[:2])}",
                    level="info",
                    action_text="View Settings",
                    action_callback="view_settings"
                )

        except Exception as e:
            logger.error(f"Error checking system status: {e}")

        return None

    def _get_motivational_tip(self) -> Suggestion:
        """
        Get a motivational tip when there are no urgent suggestions.

        Returns:
            Motivational suggestion
        """
        tips = [
            {
                "title": "Looking Good!",
                "message": "Everything is up to date. Great job staying organized!",
            },
            {
                "title": "Pro Tip",
                "message": "Use the 'Launch AI Stack' button to open all your AI tools at once.",
            },
            {
                "title": "Workflow Boost",
                "message": "Try using Workflow Groups to launch multiple related tools together.",
            },
            {
                "title": "Agent Power",
                "message": "Queue tasks for AI agents to automate research and analysis.",
            },
            {
                "title": "Stay Focused",
                "message": "Check your 'Next Best Move' to see what to work on first.",
            },
        ]

        import random
        tip = random.choice(tips)

        return Suggestion(
            suggestion_id=f"tip_{datetime.now().strftime('%Y%m%d')}",
            title=tip["title"],
            message=tip["message"],
            level="info",
            dismissable=True
        )

    def dismiss_suggestion(self, suggestion_id: str) -> None:
        """
        Dismiss a suggestion.

        Args:
            suggestion_id: ID of suggestion to dismiss
        """
        if suggestion_id not in self.dismissed_suggestions:
            self.dismissed_suggestions.append(suggestion_id)
            logger.info(f"Suggestion dismissed: {suggestion_id}")

    def get_next_best_move_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get a summary of the next best action to take.

        Returns:
            Dictionary with next best move info
        """
        try:
            # Import here to avoid circular dependency
            from command_center.todo_manager9 import TodoManager

            manager = TodoManager()
            next_task = manager.get_next_best_move()

            if next_task:
                return {
                    'task_id': next_task.task_id,
                    'title': next_task.title,
                    'description': next_task.description,
                    'project': next_task.project,
                    'priority': next_task.priority,
                    'score': next_task.ai_score,
                    'reason': f"This is your highest-priority {next_task.priority.lower()} task in {next_task.project}."
                }

        except Exception as e:
            logger.error(f"Error getting next best move: {e}")

        return None

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive dashboard summary.

        Returns:
            Dictionary with dashboard statistics
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'suggestions': [],
            'next_best_move': None,
            'quick_stats': {}
        }

        try:
            # Get suggestions
            suggestions = self.scan_for_suggestions()
            summary['suggestions'] = [s.to_dict() for s in suggestions]

            # Get next best move
            summary['next_best_move'] = self.get_next_best_move_summary()

            # Get quick stats
            summary['quick_stats'] = self._get_quick_stats()

        except Exception as e:
            logger.error(f"Error generating dashboard summary: {e}")

        return summary

    def _get_quick_stats(self) -> Dict[str, Any]:
        """
        Get quick statistics for dashboard.

        Returns:
            Dictionary with statistics
        """
        stats = {}

        try:
            # Task stats
            from command_center.todo_manager9 import TodoManager
            todo_mgr = TodoManager()
            todo_stats = todo_mgr.get_statistics()
            stats['tasks'] = {
                'total': todo_stats.get('total_tasks', 0),
                'todo': todo_stats.get('by_status', {}).get('Todo', 0),
                'in_progress': todo_stats.get('by_status', {}).get('In Progress', 0),
            }

            # Deal stats
            from command_center.deals_engine9 import DealsEngine
            deals_engine = DealsEngine()
            deal_stats = deals_engine.get_statistics()
            stats['deals'] = {
                'total': deal_stats.get('total_deals', 0),
                'total_value': deal_stats.get('total_estimated_value', 0),
            }

            # Agent stats
            from command_center.agents_manager9 import AgentsManager
            agents_mgr = AgentsManager()
            agent_stats = agents_mgr.get_statistics()
            stats['agents'] = {
                'active': agent_stats.get('active_agents', 0),
                'queued_tasks': agent_stats.get('by_status', {}).get('Queued', 0),
            }

        except Exception as e:
            logger.error(f"Error getting quick stats: {e}")

        return stats


# Convenience function
def get_dashboard_suggestions() -> List[Suggestion]:
    """
    Quick function to get dashboard suggestions.

    Returns:
        List of suggestions
    """
    helper = HelperSuggestions()
    return helper.scan_for_suggestions()


if __name__ == "__main__":
    # Test the helper suggestions
    print("Testing HelperSuggestions...")

    helper = HelperSuggestions()

    print("\nScanning for suggestions...")
    suggestions = helper.scan_for_suggestions()

    print(f"\nFound {len(suggestions)} suggestion(s):")
    for suggestion in suggestions:
        level_emoji = {
            'info': 'ℹ️',
            'tip': '💡',
            'warning': '⚠️',
            'critical': '🚨'
        }
        emoji = level_emoji.get(suggestion.level, 'ℹ️')
        print(f"\n{emoji} {suggestion.title}")
        print(f"   {suggestion.message}")

    # Get next best move
    next_move = helper.get_next_best_move_summary()
    if next_move:
        print(f"\n🎯 Next Best Move:")
        print(f"   {next_move['title']}")
        print(f"   Score: {next_move['score']}/100")

    # Get full dashboard summary
    print("\n" + "="*60)
    summary = helper.get_dashboard_summary()
    print(f"Dashboard Summary:")
    print(f"  Tasks: {summary['quick_stats'].get('tasks', {})}")
    print(f"  Deals: {summary['quick_stats'].get('deals', {})}")
    print(f"  Agents: {summary['quick_stats'].get('agents', {})}")
