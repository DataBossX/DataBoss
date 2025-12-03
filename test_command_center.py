"""
Test script for DataBossX Command Center v9
Tests all core modules to ensure they work correctly
"""

import sys
from pathlib import Path

def test_config():
    """Test configuration manager"""
    print("Testing config_databossx9...")
    try:
        from config_databossx9 import get_config
        config = get_config()
        version = config.get('system', 'version')
        print(f"  ✓ Config loaded. Version: {version}")
        return True
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return False


def test_todo_manager():
    """Test todo manager"""
    print("\nTesting todo_manager9...")
    try:
        from todo_manager9 import TodoManager
        manager = TodoManager()

        # Add a test task
        task_id = manager.add_task(
            title="Test Task",
            description="This is a test",
            project="System",
            priority="Medium"
        )
        print(f"  ✓ Created task: {task_id}")

        # Get tasks
        tasks = manager.get_tasks(limit=5)
        print(f"  ✓ Retrieved {len(tasks)} tasks")

        # Get stats
        stats = manager.get_statistics()
        print(f"  ✓ Stats: {stats.get('total_tasks', 0)} total tasks")

        return True
    except Exception as e:
        print(f"  ✗ TodoManager error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_links_manager():
    """Test links manager"""
    print("\nTesting links_manager9...")
    try:
        from links_manager9 import LinksManager
        manager = LinksManager()

        # Get all links
        links = manager.get_all_links()
        print(f"  ✓ Loaded {len(links)} links")

        # Get categories
        categories = manager.get_categories()
        print(f"  ✓ Categories: {', '.join(categories[:5])}")

        # Get workflow groups
        workflows = manager.get_workflow_groups()
        print(f"  ✓ Workflow groups: {len(workflows)}")

        return True
    except Exception as e:
        print(f"  ✗ LinksManager error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agents_manager():
    """Test agents manager"""
    print("\nTesting agents_manager9...")
    try:
        from agents_manager9 import AgentsManager
        manager = AgentsManager()

        # Get all agents
        agents = manager.get_all_agents()
        print(f"  ✓ Loaded {len(agents)} agents")

        # List agents
        for agent_id, agent in list(agents.items())[:3]:
            print(f"    - {agent['name']}: {agent['role']}")

        # Queue a task
        task_id = manager.queue_task(
            "builder",
            "Test task",
            "This is a test task for the builder agent"
        )
        print(f"  ✓ Queued task: {task_id}")

        return True
    except Exception as e:
        print(f"  ✗ AgentsManager error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ocr_orchestrator():
    """Test OCR orchestrator"""
    print("\nTesting title_ocr_orchestrator9...")
    try:
        from title_ocr_orchestrator9 import TitleOCROrchestrator
        orchestrator = TitleOCROrchestrator()

        # Get stats
        stats = orchestrator.get_document_stats()
        print(f"  ✓ Document stats retrieved")
        print(f"    - Total processed: {stats.get('total_processed', 0)}")
        print(f"    - Pending input: {stats['input_folder']['unprocessed']}")

        return True
    except Exception as e:
        print(f"  ✗ OCROrchestrator error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deals_engine():
    """Test deals engine"""
    print("\nTesting deals_engine9...")
    try:
        from deals_engine9 import DealsEngine
        engine = DealsEngine()

        # Add a test deal
        deal_id = engine.add_deal(
            deal_type="Test",
            title="Test Deal",
            description="This is a test deal",
            estimated_value=10000,
            difficulty_level="Medium"
        )
        print(f"  ✓ Created deal: {deal_id}")

        # Get stats
        stats = engine.get_statistics()
        print(f"  ✓ Stats: {stats.get('total_deals', 0)} total deals")

        return True
    except Exception as e:
        print(f"  ✗ DealsEngine error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_helper_suggestions():
    """Test helper suggestions"""
    print("\nTesting helper_suggestions9...")
    try:
        from helper_suggestions9 import HelperSuggestions
        helper = HelperSuggestions()

        # Get suggestions
        suggestions = helper.get_all_suggestions()
        print(f"  ✓ Generated {len(suggestions)} suggestions")

        # Get next best move
        next_move = helper.get_next_best_move()
        print(f"  ✓ Next best move: {next_move['title']}")

        return True
    except Exception as e:
        print(f"  ✗ HelperSuggestions error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("DataBossX Command Center v9 - Module Tests")
    print("=" * 60)

    results = {
        "Configuration": test_config(),
        "Todo Manager": test_todo_manager(),
        "Links Manager": test_links_manager(),
        "Agents Manager": test_agents_manager(),
        "OCR Orchestrator": test_ocr_orchestrator(),
        "Deals Engine": test_deals_engine(),
        "Helper Suggestions": test_helper_suggestions()
    }

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")

    print("-" * 60)
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed! Command Center is ready to use.")
        print("\nTo launch the dashboard, run:")
        print("  streamlit run databossx_dashboard9.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
