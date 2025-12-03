"""
DataBossX Command Center Dashboard v9
Production-grade Streamlit dashboard - Central control panel for DataBossX ecosystem
"""

import streamlit as st
import logging
from datetime import datetime
from pathlib import Path
import json

# Import all manager modules
from config_databossx9 import get_config
from todo_manager9 import TodoManager
from links_manager9 import LinksManager
from agents_manager9 import AgentsManager
from title_ocr_orchestrator9 import TitleOCROrchestrator
from deals_engine9 import DealsEngine
from helper_suggestions9 import HelperSuggestions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('databossx_log9.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="DataBossX Command Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark mode
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stApp {
        background-color: #0e1117;
    }
    h1, h2, h3 {
        color: #00ffff;
    }
    .big-button {
        font-size: 24px;
        font-weight: bold;
        padding: 20px;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        margin: 20px 0;
    }
    .metric-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #00ffff;
    }
    .suggestion-box {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 3px solid #ba55d3;
    }
</style>
""", unsafe_allow_html=True)


# Initialize managers (with caching)
@st.cache_resource
def init_managers():
    """Initialize all manager instances"""
    return {
        'config': get_config(),
        'todo': TodoManager(),
        'links': LinksManager(),
        'agents': AgentsManager(),
        'ocr': TitleOCROrchestrator(),
        'deals': DealsEngine(),
        'helper': HelperSuggestions()
    }


def render_sidebar():
    """Render sidebar navigation"""
    with st.sidebar:
        # Logo
        logo_path = Path("assets/databossx_logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=200)
        else:
            st.title("🚀 DataBossX")

        st.markdown("---")

        # Navigation
        tab = st.radio(
            "Navigation",
            ["Overview", "To Do", "Apps & Links", "Agents", "Title & OCR", "Money & Deals", "Settings"],
            label_visibility="collapsed"
        )

        st.markdown("---")

        # Quick stats
        st.subheader("Quick Stats")
        managers = init_managers()

        try:
            task_stats = managers['todo'].get_statistics()
            st.metric("Active Tasks", task_stats.get('by_status', {}).get('To Do', 0))

            deal_stats = managers['deals'].get_statistics()
            st.metric("Active Deals", deal_stats.get('by_status', {}).get('New', 0))

            doc_stats = managers['ocr'].get_document_stats()
            pending_docs = doc_stats.get('input_folder', {}).get('unprocessed', 0)
            st.metric("Pending Docs", pending_docs)
        except Exception as e:
            logger.error(f"Error loading stats: {e}")

    return tab


def render_overview():
    """Render Overview tab"""
    st.title("📊 DataBossX Command Center")
    st.markdown("### Your Central Control Panel")

    managers = init_managers()

    # Welcome section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Welcome Back, DataBoss! 👋")
        current_time = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
        st.write(f"**{current_time}**")

        # Next Best Move
        st.markdown("---")
        st.markdown("### 🎯 Next Best Move")

        try:
            next_move = managers['helper'].get_next_best_move()
            st.markdown(f"""
            <div class="suggestion-box">
                <h3>{next_move['icon']} {next_move['title']}</h3>
                <p>{next_move['description']}</p>
            </div>
            """, unsafe_allow_html=True)

            if next_move.get('action_label'):
                if st.button(next_move['action_label'], key="next_move_btn"):
                    st.success(f"Action: {next_move['action']}")
        except Exception as e:
            logger.error(f"Error getting next move: {e}")
            st.info("No urgent actions at the moment. You're all caught up!")

    with col2:
        # Launch AI Stack button
        st.markdown("### 🚀 Quick Actions")

        if st.button("🤖 Launch AI Stack", key="ai_stack", help="Open all AI tools"):
            try:
                managers['links'].open_workflow_group("ai_stack")
                st.success("AI Stack launched! Check your browser tabs.")
            except Exception as e:
                st.error(f"Error: {e}")

        if st.button("📁 Open Penterra", key="penterra"):
            try:
                managers['links'].open_link("penterra_sharefile")
                st.success("Opening Penterra ShareFile...")
            except Exception as e:
                st.error(f"Error: {e}")

        if st.button("📧 Open AOL", key="aol"):
            try:
                managers['links'].open_link("aol_mail")
                st.success("Opening AOL Mail...")
            except Exception as e:
                st.error(f"Error: {e}")

    # System Overview
    st.markdown("---")
    st.markdown("### 📈 System Overview")

    col1, col2, col3, col4 = st.columns(4)

    try:
        task_stats = managers['todo'].get_statistics()
        deal_stats = managers['deals'].get_statistics()
        doc_stats = managers['ocr'].get_document_stats()

        with col1:
            st.metric(
                "Total Tasks",
                task_stats.get('total_tasks', 0),
                f"{task_stats.get('completion_rate', 0):.1f}% complete"
            )

        with col2:
            st.metric(
                "Pipeline Value",
                f"${deal_stats.get('total_pipeline_value', 0):,.0f}",
                f"{deal_stats.get('high_priority_deals', 0)} high priority"
            )

        with col3:
            st.metric(
                "Processed Docs",
                doc_stats.get('total_processed', 0),
                f"{doc_stats.get('input_folder', {}).get('unprocessed', 0)} pending"
            )

        with col4:
            agent_count = len(managers['agents'].get_all_agents())
            st.metric(
                "Active Agents",
                agent_count,
                "Ready"
            )
    except Exception as e:
        logger.error(f"Error loading overview stats: {e}")

    # Suggestions
    st.markdown("---")
    st.markdown("### 💡 Suggestions & Tips")

    try:
        suggestions = managers['helper'].get_all_suggestions()[:5]
        for sug in suggestions:
            priority_color = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Low': '🟢',
                'Info': '🔵'
            }.get(sug['priority'], '⚪')

            st.markdown(f"""
            <div class="suggestion-box">
                {priority_color} {sug['icon']} <strong>{sug['title']}</strong><br>
                <small>{sug['description']}</small>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error loading suggestions: {e}")


def render_todo():
    """Render To Do tab"""
    st.title("✅ Task Manager")

    managers = init_managers()

    # Filter controls
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        project_filter = st.selectbox(
            "Project",
            ["All"] + managers['config'].get('tasks', 'projects', []),
            key="task_project_filter"
        )

    with col2:
        status_filter = st.selectbox(
            "Status",
            ["All"] + managers['config'].get('tasks', 'status_options', []),
            key="task_status_filter"
        )

    with col3:
        priority_filter = st.selectbox(
            "Priority",
            ["All"] + managers['config'].get('tasks', 'priority_levels', []),
            key="task_priority_filter"
        )

    with col4:
        st.write("")  # Spacer
        if st.button("➕ New Task", key="new_task_btn"):
            st.session_state['show_new_task'] = True

    # Get filtered tasks
    try:
        tasks = managers['todo'].get_tasks(
            project=None if project_filter == "All" else project_filter,
            status=None if status_filter == "All" else status_filter,
            priority=None if priority_filter == "All" else priority_filter,
            limit=100
        )

        # Update AI scores
        managers['todo'].update_all_ai_scores()

        # Display tasks
        st.markdown("---")
        st.markdown(f"### Tasks ({len(tasks)} found)")

        for task in tasks:
            with st.expander(
                f"{'✅' if task['status'] == 'Done' else '⏳'} {task['title']} "
                f"[{task['priority']}] [Score: {task.get('ai_score', 0):.0f}]"
            ):
                st.write(f"**Project:** {task['project']}")
                st.write(f"**Status:** {task['status']}")
                st.write(f"**Priority:** {task['priority']}")
                st.write(f"**Description:** {task.get('description', 'No description')}")
                if task.get('due_date'):
                    st.write(f"**Due Date:** {task['due_date']}")
                st.write(f"**Created:** {task['created_at']}")

                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Mark Done", key=f"done_{task['id']}"):
                        managers['todo'].update_task(task['id'], status="Done")
                        st.rerun()
                with col2:
                    if st.button("Edit", key=f"edit_{task['id']}"):
                        st.info("Edit functionality - implement as needed")
                with col3:
                    if st.button("Delete", key=f"delete_{task['id']}"):
                        managers['todo'].delete_task(task['id'])
                        st.rerun()

    except Exception as e:
        logger.error(f"Error loading tasks: {e}")
        st.error(f"Error loading tasks: {e}")

    # New task form
    if st.session_state.get('show_new_task', False):
        st.markdown("---")
        st.markdown("### ➕ Create New Task")

        with st.form("new_task_form"):
            title = st.text_input("Title *")
            description = st.text_area("Description")
            col1, col2 = st.columns(2)
            with col1:
                project = st.selectbox("Project", managers['config'].get('tasks', 'projects', []))
                priority = st.selectbox("Priority", managers['config'].get('tasks', 'priority_levels', []))
            with col2:
                status = st.selectbox("Status", managers['config'].get('tasks', 'status_options', []))
                due_date = st.date_input("Due Date")

            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Create Task")
            with col2:
                cancel = st.form_submit_button("Cancel")

            if submit and title:
                try:
                    task_id = managers['todo'].add_task(
                        title=title,
                        description=description,
                        project=project,
                        priority=priority,
                        status=status,
                        due_date=due_date.isoformat() if due_date else None
                    )
                    st.success(f"Task created: {task_id}")
                    st.session_state['show_new_task'] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating task: {e}")

            if cancel:
                st.session_state['show_new_task'] = False
                st.rerun()


def render_links():
    """Render Apps & Links tab"""
    st.title("🔗 Apps & Links Hub")

    managers = init_managers()

    # Launch AI Stack button (prominent)
    st.markdown("""
    <div class="big-button">
        🚀 Launch AI Stack
    </div>
    """, unsafe_allow_html=True)

    if st.button("Click to Launch All AI Tools", key="launch_ai_stack_main", use_container_width=True):
        try:
            managers['links'].open_workflow_group("ai_stack")
            st.success("🚀 AI Stack launched! Check your browser tabs.")
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")

    # Workflow Groups
    st.markdown("### 🎯 Workflow Groups")

    workflow_groups = managers['links'].get_workflow_groups()
    cols = st.columns(3)

    for idx, (group_id, group) in enumerate(workflow_groups.items()):
        with cols[idx % 3]:
            st.markdown(f"**{group['icon']} {group['name']}**")
            st.write(group['description'])
            if st.button(f"Launch", key=f"workflow_{group_id}"):
                try:
                    managers['links'].open_workflow_group(group_id)
                    st.success(f"Launched {group['name']}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")

    # All Links by Category
    st.markdown("### 📑 All Links")

    categories = managers['links'].get_categories()
    selected_category = st.selectbox("Filter by Category", ["All"] + categories)

    if selected_category == "All":
        links = managers['links'].get_all_links()
    else:
        links = managers['links'].get_links_by_category(selected_category)

    # Display links in grid
    cols = st.columns(4)
    for idx, (link_id, link) in enumerate(links.items()):
        with cols[idx % 4]:
            st.markdown(f"**{link['icon']} {link['name']}**")
            st.caption(link.get('description', ''))
            if st.button("Open", key=f"link_{link_id}"):
                try:
                    managers['links'].open_link(link_id)
                    st.success(f"Opening {link['name']}")
                except Exception as e:
                    st.error(f"Error: {e}")


def render_agents():
    """Render Agents tab"""
    st.title("🤖 Agent Console")

    managers = init_managers()

    # Agent cards
    st.markdown("### Available Agents")

    agents = managers['agents'].get_all_agents()
    cols = st.columns(3)

    for idx, (agent_id, agent) in enumerate(agents.items()):
        with cols[idx % 3]:
            st.markdown(f"### {agent['icon']} {agent['name']}")
            st.write(f"**Role:** {agent['role']}")
            st.write(agent['description'])
            st.caption(f"Specialties: {', '.join(agent['specialties'][:3])}")

            # Get agent stats
            try:
                stats = managers['agents'].get_agent_stats(agent_id)
                st.metric("Tasks Completed", stats.get('by_status', {}).get('completed', 0))
            except:
                pass

    st.markdown("---")

    # Queue new task
    st.markdown("### 📝 Queue New Agent Task")

    with st.form("agent_task_form"):
        selected_agent = st.selectbox(
            "Select Agent",
            list(agents.keys()),
            format_func=lambda x: f"{agents[x]['icon']} {agents[x]['name']}"
        )

        task_title = st.text_input("Task Title *")
        task_description = st.text_area("Task Description *")
        priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])

        if st.form_submit_button("Queue Task"):
            if task_title and task_description:
                try:
                    task_id = managers['agents'].queue_task(
                        selected_agent,
                        task_title,
                        task_description,
                        priority=priority
                    )
                    st.success(f"Task queued: {task_id}")

                    # Process immediately
                    if st.checkbox("Process Now", value=True):
                        with st.spinner("Processing..."):
                            managers['agents'].process_task(task_id)
                            st.success("Task processed!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")

    # Recent tasks
    st.markdown("### 📋 Recent Agent Tasks")

    try:
        recent_tasks = managers['agents'].get_all_tasks(limit=10)
        for task in recent_tasks:
            agent = agents.get(task['agent_id'], {})
            status_icon = {'queued': '⏳', 'processing': '⚙️', 'completed': '✅', 'failed': '❌'}

            with st.expander(f"{status_icon.get(task['status'], '❓')} {task['task_title']} [{agent.get('name', task['agent_id'])}]"):
                st.write(f"**Description:** {task['task_description']}")
                st.write(f"**Status:** {task['status']}")
                st.write(f"**Requested:** {task['requested_at']}")
                if task.get('result'):
                    st.write("**Result:**")
                    st.code(task['result'][:500])
    except Exception as e:
        logger.error(f"Error loading agent tasks: {e}")


def render_title_ocr():
    """Render Title & OCR tab"""
    st.title("📄 Title & OCR Workflow")

    managers = init_managers()

    # Document stats
    try:
        stats = managers['ocr'].get_document_stats()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Input Folder", stats['input_folder']['total'],
                     f"{stats['input_folder']['unprocessed']} pending")
        with col2:
            st.metric("Penterra Folder", stats['penterra_folder']['total'],
                     f"{stats['penterra_folder']['unprocessed']} pending")
        with col3:
            st.metric("Total Processed", stats['total_processed'])
    except Exception as e:
        logger.error(f"Error loading OCR stats: {e}")

    st.markdown("---")

    # Action buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Scan for Documents", use_container_width=True):
            with st.spinner("Scanning..."):
                docs = managers['ocr'].scan_for_documents()
                st.success(f"Found {len(docs)} documents")
                st.json({
                    'total': len(docs),
                    'unprocessed': sum(1 for d in docs if not d['processed'])
                })

    with col2:
        if st.button("🏆 Run OCR Tournament", use_container_width=True):
            st.info("OCR Tournament feature - processes documents with multiple engines")

    st.markdown("---")

    # Extraction results
    st.markdown("### 📊 Recent Extraction Results")

    try:
        results = managers['ocr'].get_extraction_results(limit=20)

        for result in results:
            with st.expander(f"📄 {result['filename']} - Confidence: {result['confidence_score']:.2%}"):
                st.write(f"**Status:** {result['status']}")
                st.write(f"**Processed:** {result['upload_time']}")

                if result.get('extracted_data'):
                    st.markdown("**Extracted Data:**")
                    st.json(result['extracted_data'])
    except Exception as e:
        logger.error(f"Error loading extraction results: {e}")


def render_deals():
    """Render Money & Deals tab"""
    st.title("💰 Money & Deals Engine")

    managers = init_managers()

    # Stats
    try:
        stats = managers['deals'].get_statistics()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Deals", stats['total_deals'])
        with col2:
            st.metric("Pipeline Value", f"${stats['total_pipeline_value']:,.0f}")
        with col3:
            st.metric("Total Revenue", f"${stats['total_revenue']:,.0f}")
        with col4:
            st.metric("High Priority", stats['high_priority_deals'])
    except Exception as e:
        logger.error(f"Error loading deal stats: {e}")

    st.markdown("---")

    # Top Deals
    st.markdown("### 🏆 Top Deals")

    try:
        top_deals = managers['deals'].get_top_deals(limit=10)

        for deal in top_deals:
            with st.expander(
                f"{'💎' if deal['deal_score'] >= 80 else '💰'} {deal['title']} "
                f"[Score: {deal['deal_score']:.0f}/100] [${deal['estimated_value']:,.0f}]"
            ):
                st.write(f"**Type:** {deal['deal_type']}")
                st.write(f"**Prospect:** {deal.get('prospect_name', 'Unknown')}")
                st.write(f"**Property:** {deal.get('property_address', 'N/A')}")
                st.write(f"**Estimated Value:** ${deal['estimated_value']:,.2f}")
                st.write(f"**Difficulty:** {deal.get('difficulty_level', 'Unknown')}")
                st.write(f"**Description:** {deal.get('description', '')}")

                if st.button("📧 Generate Contact Package", key=f"contact_{deal['id']}"):
                    with st.spinner("Generating..."):
                        package = managers['deals'].generate_contact_package(deal['id'])
                        st.success("Contact package generated!")
                        st.markdown("**Email Subject:**")
                        st.code(package['email_subject'])
                        st.markdown("**Email Body:**")
                        st.text_area("Email", package['email_body'], height=200, key=f"email_{deal['id']}")
    except Exception as e:
        logger.error(f"Error loading deals: {e}")
        st.error(f"Error loading deals: {e}")


def render_settings():
    """Render Settings tab"""
    st.title("⚙️ Settings")

    managers = init_managers()
    config = managers['config']

    st.markdown("### System Configuration")

    # Paths
    with st.expander("📁 Paths", expanded=False):
        paths = config.get('paths')
        for key, value in paths.items():
            new_value = st.text_input(key, value, key=f"path_{key}")
            if new_value != value:
                config.set('paths', key, new_value)

    # UI Settings
    with st.expander("🎨 UI Settings", expanded=False):
        ui = config.get('ui')
        theme = st.selectbox("Theme", ["dark", "light"], index=0 if ui.get('theme') == 'dark' else 1)
        show_tips = st.checkbox("Show Tips", value=ui.get('show_tips', True))

        if theme != ui.get('theme'):
            config.set('ui', 'theme', theme)
        if show_tips != ui.get('show_tips'):
            config.set('ui', 'show_tips', show_tips)

    # Tasks Settings
    with st.expander("✅ Tasks Settings", expanded=False):
        tasks = config.get('tasks')
        projects = st.text_area("Projects (one per line)", "\n".join(tasks.get('projects', [])))
        if st.button("Update Projects"):
            config.set('tasks', 'projects', [p.strip() for p in projects.split('\n') if p.strip()])
            st.success("Projects updated!")

    # Export/Import
    st.markdown("---")
    st.markdown("### 💾 Backup & Restore")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export Configuration"):
            export_path = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            config.export_config(export_path)
            st.success(f"Configuration exported to {export_path}")

    with col2:
        if st.button("Reset to Defaults"):
            if st.checkbox("Confirm Reset"):
                config.reset_to_defaults()
                st.success("Configuration reset to defaults")
                st.rerun()


def main():
    """Main application entry point"""
    try:
        # Render sidebar and get selected tab
        current_tab = render_sidebar()

        # Render selected tab
        if current_tab == "Overview":
            render_overview()
        elif current_tab == "To Do":
            render_todo()
        elif current_tab == "Apps & Links":
            render_links()
        elif current_tab == "Agents":
            render_agents()
        elif current_tab == "Title & OCR":
            render_title_ocr()
        elif current_tab == "Money & Deals":
            render_deals()
        elif current_tab == "Settings":
            render_settings()

    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        st.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
