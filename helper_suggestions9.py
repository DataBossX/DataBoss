"""
DataBossX Helper Suggestions v9
Background helper system that provides intelligent tips and suggestions
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from config_databossx9 import get_config
from todo_manager9 import TodoManager
from deals_engine9 import DealsEngine
from title_ocr_orchestrator9 import TitleOCROrchestrator

# Configure logging
logger = logging.getLogger(__name__)


class HelperSuggestions:
    """
    Provides intelligent suggestions and tips based on system state.
    Acts as a background assistant highlighting important items.
    """

    def __init__(self):
        """Initialize Helper Suggestions system"""
        self.config = get_config()
        self.todo_manager = TodoManager()
        self.deals_engine = DealsEngine()
        self.ocr_orchestrator = TitleOCROrchestrator()
        logger.info("HelperSuggestions initialized")

    def get_all_suggestions(self) -> List[Dict[str, Any]]:
        """
        Get all active suggestions.

        Returns:
            List of suggestion dictionaries
        """
        suggestions = []

        # Check for unprocessed documents
        suggestions.extend(self._check_unprocessed_documents())

        # Check for high-priority tasks
        suggestions.extend(self._check_priority_tasks())

        # Check for high-value deals
        suggestions.extend(self._check_deals())

        # Check for overdue tasks
        suggestions.extend(self._check_overdue_tasks())

        # Check for blocked tasks
        suggestions.extend(self._check_blocked_tasks())

        # Check system health
        suggestions.extend(self._check_system_health())

        # Sort by priority
        suggestions.sort(key=lambda x: self._get_priority_value(x['priority']), reverse=True)

        return suggestions

    def _get_priority_value(self, priority: str) -> int:
        """Convert priority to numeric value"""
        priority_map = {
            'Critical': 4,
            'High': 3,
            'Medium': 2,
            'Low': 1,
            'Info': 0
        }
        return priority_map.get(priority, 0)

    def _check_unprocessed_documents(self) -> List[Dict[str, Any]]:
        """Check for unprocessed documents"""
        suggestions = []

        try:
            stats = self.ocr_orchestrator.get_document_stats()

            # Check input folder
            if stats['input_folder']['unprocessed'] > 0:
                suggestions.append({
                    'type': 'document_processing',
                    'priority': 'High',
                    'icon': '📄',
                    'title': f"{stats['input_folder']['unprocessed']} unprocessed documents in input folder",
                    'description': "You have documents waiting to be processed with OCR",
                    'action': 'process_documents',
                    'action_label': 'Process Now',
                    'data': {'folder': 'input', 'count': stats['input_folder']['unprocessed']}
                })

            # Check Penterra folder
            if stats['penterra_folder']['unprocessed'] > 0:
                suggestions.append({
                    'type': 'document_processing',
                    'priority': 'High',
                    'icon': '📁',
                    'title': f"{stats['penterra_folder']['unprocessed']} unprocessed Penterra PDFs",
                    'description': "Penterra documents need OCR processing and data extraction",
                    'action': 'process_penterra',
                    'action_label': 'Process Penterra Docs',
                    'data': {'folder': 'penterra', 'count': stats['penterra_folder']['unprocessed']}
                })

        except Exception as e:
            logger.error(f"Error checking documents: {e}")

        return suggestions

    def _check_priority_tasks(self) -> List[Dict[str, Any]]:
        """Check for high-priority tasks"""
        suggestions = []

        try:
            # Get high priority tasks
            high_priority_tasks = self.todo_manager.get_tasks(
                priority="High",
                status="To Do",
                limit=5
            )

            if high_priority_tasks:
                suggestions.append({
                    'type': 'tasks',
                    'priority': 'High',
                    'icon': '⚡',
                    'title': f"{len(high_priority_tasks)} high-priority tasks pending",
                    'description': f"Top task: {high_priority_tasks[0]['title']}",
                    'action': 'view_tasks',
                    'action_label': 'View Tasks',
                    'data': {'tasks': high_priority_tasks}
                })

            # Get critical priority tasks
            critical_tasks = self.todo_manager.get_tasks(
                priority="Critical",
                status="To Do",
                limit=10
            )

            if critical_tasks:
                suggestions.append({
                    'type': 'tasks',
                    'priority': 'Critical',
                    'icon': '🚨',
                    'title': f"{len(critical_tasks)} CRITICAL tasks require attention!",
                    'description': f"Most urgent: {critical_tasks[0]['title']}",
                    'action': 'view_critical_tasks',
                    'action_label': 'View Critical Tasks',
                    'data': {'tasks': critical_tasks}
                })

        except Exception as e:
            logger.error(f"Error checking tasks: {e}")

        return suggestions

    def _check_deals(self) -> List[Dict[str, Any]]:
        """Check for high-value deals"""
        suggestions = []

        try:
            # Get top deals
            top_deals = self.deals_engine.get_top_deals(limit=5)

            if top_deals:
                total_value = sum(deal['estimated_value'] for deal in top_deals)
                suggestions.append({
                    'type': 'deals',
                    'priority': 'High',
                    'icon': '💰',
                    'title': f"{len(top_deals)} high-value deals in pipeline",
                    'description': f"Total potential value: ${total_value:,.2f}",
                    'action': 'view_deals',
                    'action_label': 'View Deals',
                    'data': {'deals': top_deals, 'total_value': total_value}
                })

            # Check for deals needing contact
            new_deals = self.deals_engine.get_deals(status="New", limit=10)
            if new_deals:
                suggestions.append({
                    'type': 'deals',
                    'priority': 'Medium',
                    'icon': '📞',
                    'title': f"{len(new_deals)} deals ready for outreach",
                    'description': "Generate contact packages and start communications",
                    'action': 'generate_contacts',
                    'action_label': 'Generate Contact Packages',
                    'data': {'deals': new_deals}
                })

        except Exception as e:
            logger.error(f"Error checking deals: {e}")

        return suggestions

    def _check_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Check for overdue tasks"""
        suggestions = []

        try:
            all_tasks = self.todo_manager.get_tasks(limit=500)
            overdue_tasks = []

            now = datetime.now()
            for task in all_tasks:
                if task.get('due_date') and task['status'] != 'Done':
                    try:
                        due_date = datetime.fromisoformat(task['due_date'])
                        if due_date < now:
                            overdue_tasks.append(task)
                    except:
                        pass

            if overdue_tasks:
                suggestions.append({
                    'type': 'tasks',
                    'priority': 'Critical',
                    'icon': '⏰',
                    'title': f"{len(overdue_tasks)} overdue tasks!",
                    'description': "These tasks are past their due date",
                    'action': 'view_overdue',
                    'action_label': 'View Overdue Tasks',
                    'data': {'tasks': overdue_tasks}
                })

        except Exception as e:
            logger.error(f"Error checking overdue tasks: {e}")

        return suggestions

    def _check_blocked_tasks(self) -> List[Dict[str, Any]]:
        """Check for blocked tasks"""
        suggestions = []

        try:
            blocked_tasks = self.todo_manager.get_tasks(status="Blocked", limit=10)

            if blocked_tasks:
                suggestions.append({
                    'type': 'tasks',
                    'priority': 'High',
                    'icon': '🚧',
                    'title': f"{len(blocked_tasks)} blocked tasks need resolution",
                    'description': "Review blockers and take action to unblock",
                    'action': 'view_blocked',
                    'action_label': 'View Blocked Tasks',
                    'data': {'tasks': blocked_tasks}
                })

        except Exception as e:
            logger.error(f"Error checking blocked tasks: {e}")

        return suggestions

    def _check_system_health(self) -> List[Dict[str, Any]]:
        """Check system health and suggest actions"""
        suggestions = []

        try:
            # Check task completion rate
            stats = self.todo_manager.get_statistics()
            completion_rate = stats.get('completion_rate', 0)

            if completion_rate < 30:
                suggestions.append({
                    'type': 'system',
                    'priority': 'Medium',
                    'icon': '📊',
                    'title': f"Task completion rate is low ({completion_rate:.1f}%)",
                    'description': "Consider reviewing and closing completed tasks",
                    'action': 'review_tasks',
                    'action_label': 'Review Tasks',
                    'data': {'completion_rate': completion_rate}
                })

            # Check if there are tasks but none in progress
            total_tasks = stats.get('total_tasks', 0)
            in_progress = stats.get('by_status', {}).get('In Progress', 0)

            if total_tasks > 0 and in_progress == 0:
                suggestions.append({
                    'type': 'system',
                    'priority': 'Medium',
                    'icon': '🎯',
                    'title': "No tasks currently in progress",
                    'description': "Pick a task and get started!",
                    'action': 'start_task',
                    'action_label': 'View Next Best Move',
                    'data': {}
                })

        except Exception as e:
            logger.error(f"Error checking system health: {e}")

        return suggestions

    def get_next_best_move(self) -> Dict[str, Any]:
        """
        Get the single most important action to take right now.

        Returns:
            Suggestion dictionary
        """
        all_suggestions = self.get_all_suggestions()

        if not all_suggestions:
            return {
                'type': 'system',
                'priority': 'Info',
                'icon': '✅',
                'title': "All caught up!",
                'description': "No urgent items need attention. Great job!",
                'action': None,
                'action_label': None,
                'data': {}
            }

        # Return highest priority suggestion
        return all_suggestions[0]

    def get_daily_summary(self) -> Dict[str, Any]:
        """
        Get daily summary of system state.

        Returns:
            Summary dictionary
        """
        summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'tasks': {},
            'deals': {},
            'documents': {},
            'suggestions': []
        }

        try:
            # Task summary
            task_stats = self.todo_manager.get_statistics()
            summary['tasks'] = {
                'total': task_stats.get('total_tasks', 0),
                'to_do': task_stats.get('by_status', {}).get('To Do', 0),
                'in_progress': task_stats.get('by_status', {}).get('In Progress', 0),
                'completed': task_stats.get('by_status', {}).get('Done', 0),
                'completion_rate': task_stats.get('completion_rate', 0)
            }

            # Deals summary
            deal_stats = self.deals_engine.get_statistics()
            summary['deals'] = {
                'total': deal_stats.get('total_deals', 0),
                'high_priority': deal_stats.get('high_priority_deals', 0),
                'pipeline_value': deal_stats.get('total_pipeline_value', 0),
                'revenue': deal_stats.get('total_revenue', 0)
            }

            # Documents summary
            doc_stats = self.ocr_orchestrator.get_document_stats()
            summary['documents'] = {
                'total_processed': doc_stats.get('total_processed', 0),
                'pending_input': doc_stats.get('input_folder', {}).get('unprocessed', 0),
                'pending_penterra': doc_stats.get('penterra_folder', {}).get('unprocessed', 0)
            }

            # Get top 3 suggestions
            summary['suggestions'] = self.get_all_suggestions()[:3]

        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")

        return summary

    def get_productivity_tips(self) -> List[str]:
        """
        Get contextual productivity tips.

        Returns:
            List of tip strings
        """
        tips = []

        try:
            # Get next best move
            next_move = self.todo_manager.get_next_best_move()
            if next_move:
                tips.append(f"🎯 Your next best move: {next_move['title']}")

            # Check time of day for contextual tips
            hour = datetime.now().hour

            if 6 <= hour < 12:
                tips.append("☀️ Good morning! Start with your highest priority task.")
            elif 12 <= hour < 18:
                tips.append("⚡ Afternoon energy dip? Take a break or tackle some quick wins.")
            else:
                tips.append("🌙 Evening hours - great time for planning tomorrow.")

            # Workflow suggestions
            suggestions = self.get_all_suggestions()
            if any(s['type'] == 'deals' for s in suggestions):
                tips.append("💡 Tip: Use the 'Launch AI Stack' to research deals faster.")

            if any(s['type'] == 'document_processing' for s in suggestions):
                tips.append("📄 Tip: Process documents in batches for efficiency.")

        except Exception as e:
            logger.error(f"Error getting productivity tips: {e}")

        return tips[:5]  # Limit to 5 tips


if __name__ == "__main__":
    # Test the HelperSuggestions
    helper = HelperSuggestions()

    print("Daily Summary:")
    summary = helper.get_daily_summary()
    print(json.dumps(summary, indent=2))

    print("\nSuggestions:")
    suggestions = helper.get_all_suggestions()
    for sug in suggestions[:5]:
        print(f"  [{sug['priority']}] {sug['icon']} {sug['title']}")

    print("\nNext Best Move:")
    next_move = helper.get_next_best_move()
    print(f"  {next_move['icon']} {next_move['title']}")
