"""
DataBossX Command Center - Main Dashboard
The central control panel for the DataBossX ecosystem.
"""

import streamlit as st
import sys
from pathlib import Path
import webbrowser
from datetime import datetime

# Add command_center to path
sys.path.insert(0, str(Path(__file__).parent))

# Import managers
from command_center.config_databossx9 import get_config
from command_center.todo_manager9 import TodoManager, Task
from command_center.links_manager9 import LinksManager
from command_center.agents_manager9 import AgentsManager
from command_center.title_ocr_orchestrator9 import TitleOCROrchestrator
from command_center.deals_engine9 import DealsEngine, Deal
from command_center.helper_suggestions9 import HelperSuggestions

# Page configuration
st.set_page_config(
    page_title="DataBossX Command Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    /* Dark theme colors */
    :root {
        --primary-color: #00FFFF;
        --secondary-color: #8A2BE2;
        --accent-color: #FF1493;
        --bg-dark: #0A0A0F;
        --card-bg: #14141E;
    }

    /* Main container styling */
    .main {
        background-color: var(--bg-dark);
    }

    /* Card styling */
    .stApp {
        background: linear-gradient(135deg, #0A0A0F 0%, #1A0A2E 100%);
    }

    /* Headers */
    h1, h2, h3 {
        color: var(--primary-color) !important;
        font-weight: 700 !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: black;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 20px var(--primary-color);
    }

    /* Cards */
    .link-card {
        background: var(--card-bg);
        border: 2px solid var(--primary-color);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .link-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 20px var(--primary-color);
    }

    /* Status bar */
    .status-bar {
        background: var(--card-bg);
        border-left: 4px solid var(--primary-color);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }

    /* Suggestion boxes */
    .suggestion-info {
        background: #1A2332;
        border-left: 4px solid #00BFFF;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }

    .suggestion-warning {
        background: #332A1A;
        border-left: 4px solid #FFA500;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }

    .suggestion-critical {
        background: #331A1A;
        border-left: 4px solid #FF1493;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }

    /* Metrics */
    .metric-card {
        background: var(--card-bg);
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid var(--primary-color);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'config' not in st.session_state:
        st.session_state.config = get_config()

    if 'todo_manager' not in st.session_state:
        st.session_state.todo_manager = TodoManager()

    if 'links_manager' not in st.session_state:
        st.session_state.links_manager = LinksManager()

    if 'agents_manager' not in st.session_state:
        st.session_state.agents_manager = AgentsManager()

    if 'ocr_orchestrator' not in st.session_state:
        st.session_state.ocr_orchestrator = TitleOCROrchestrator()

    if 'deals_engine' not in st.session_state:
        st.session_state.deals_engine = DealsEngine()

    if 'helper' not in st.session_state:
        st.session_state.helper = HelperSuggestions()


def render_header():
    """Render the top header with logo and status."""
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        # Try to display logo if it exists
        logo_path = Path("assets/databossx_logo_small.png")
        if logo_path.exists():
            st.image(str(logo_path), width=100)
        else:
            st.markdown("### 🚀 DataBossX")

    with col2:
        st.markdown("# Command Center")
        st.markdown(f"*Your AI-Powered Control Panel* | {datetime.now().strftime('%B %d, %Y')}")

    with col3:
        # Quick status indicators
        stats = st.session_state.helper.get_dashboard_summary()
        quick_stats = stats.get('quick_stats', {})
        tasks = quick_stats.get('tasks', {})
        st.metric("Active Tasks", tasks.get('in_progress', 0))


def render_sidebar():
    """Render the sidebar navigation."""
    st.sidebar.markdown("## Navigation")

    # Main navigation
    page = st.sidebar.radio(
        "Go to",
        ["🏠 Overview", "✅ To Do", "🔗 Apps & Links", "🤖 Agents",
         "📄 Title & OCR", "💰 Money & Deals", "⚙️ Settings"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")

    # Quick actions
    st.sidebar.markdown("### Quick Actions")

    if st.sidebar.button("🚀 Launch AI Stack", use_container_width=True):
        launch_ai_stack()

    if st.sidebar.button("📊 Refresh Data", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")

    # System info
    st.sidebar.markdown("### System Info")
    st.sidebar.info(f"""
    **Version:** 9.0
    **Session:** {datetime.now().strftime('%H:%M')}
    **Status:** ✅ Online
    """)

    return page


def launch_ai_stack():
    """Launch all AI tools at once."""
    links_mgr = st.session_state.links_manager
    success = links_mgr.open_workflow_group("ai_stack")

    if success:
        st.sidebar.success("🚀 AI Stack launched!")
    else:
        st.sidebar.error("Failed to launch AI Stack")


def render_overview_page():
    """Render the Overview page."""
    st.markdown("## 🏠 Welcome to DataBossX Command Center")

    # Suggestions section
    st.markdown("### 💡 Suggestions & Alerts")

    suggestions = st.session_state.helper.scan_for_suggestions()

    if suggestions:
        for suggestion in suggestions[:5]:  # Show top 5
            level_class = f"suggestion-{suggestion.level}"
            level_emoji = {
                'info': 'ℹ️',
                'tip': '💡',
                'warning': '⚠️',
                'critical': '🚨'
            }
            emoji = level_emoji.get(suggestion.level, 'ℹ️')

            with st.container():
                st.markdown(f"""
                <div class="{level_class}">
                    <strong>{emoji} {suggestion.title}</strong><br>
                    {suggestion.message}
                </div>
                """, unsafe_allow_html=True)

                if suggestion.action_text:
                    st.button(suggestion.action_text, key=f"action_{suggestion.suggestion_id}")
    else:
        st.success("✅ All systems nominal! No urgent items.")

    st.markdown("---")

    # Next Best Move
    st.markdown("### 🎯 Next Best Move")

    next_move = st.session_state.helper.get_next_best_move_summary()

    if next_move:
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**{next_move['title']}**")
            st.write(next_move['description'])
            st.caption(f"Project: {next_move['project']} | Priority: {next_move['priority']}")

        with col2:
            st.metric("Score", f"{next_move['score']}/100")
            if st.button("Start Now", use_container_width=True):
                st.info("Task management integration here!")
    else:
        st.info("No pending tasks. Great job!")

    st.markdown("---")

    # Big Launch Button
    st.markdown("### 🚀 Quick Launch")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🚀 Launch AI Stack", key="main_ai_launch", use_container_width=True):
            launch_ai_stack()

    with col2:
        if st.button("💼 View Deals", use_container_width=True):
            st.session_state.page = "💰 Money & Deals"
            st.rerun()

    with col3:
        if st.button("✅ My Tasks", use_container_width=True):
            st.session_state.page = "✅ To Do"
            st.rerun()

    st.markdown("---")

    # Dashboard Statistics
    st.markdown("### 📊 Dashboard Statistics")

    stats = st.session_state.helper.get_dashboard_summary()
    quick_stats = stats.get('quick_stats', {})

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        tasks = quick_stats.get('tasks', {})
        st.metric("Total Tasks", tasks.get('total', 0))
        st.caption(f"📝 {tasks.get('todo', 0)} To Do | ⚡ {tasks.get('in_progress', 0)} In Progress")

    with col2:
        deals = quick_stats.get('deals', {})
        st.metric("Active Deals", deals.get('total', 0))
        st.caption(f"💵 ${deals.get('total_value', 0):,.0f} Total Value")

    with col3:
        agents = quick_stats.get('agents', {})
        st.metric("AI Agents", agents.get('active', 0))
        st.caption(f"📋 {agents.get('queued_tasks', 0)} Queued Tasks")

    with col4:
        docs = st.session_state.ocr_orchestrator.scan_for_documents()
        st.metric("Documents", len(docs))
        st.caption("📄 Ready for processing")


def render_todo_page():
    """Render the To-Do page."""
    st.markdown("## ✅ Task Management")

    todo_mgr = st.session_state.todo_manager

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        project_filter = st.selectbox(
            "Project",
            ["All", "Penterra", "Genealogy", "System"]
        )

    with col2:
        priority_filter = st.selectbox(
            "Priority",
            ["All", "Critical", "High", "Medium", "Low"]
        )

    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All", "Todo", "In Progress", "Blocked", "Done"]
        )

    # Apply filters
    project = None if project_filter == "All" else project_filter
    priority = None if priority_filter == "All" else priority_filter
    status = None if status_filter == "All" else status_filter

    tasks = todo_mgr.get_tasks(project=project, priority=priority, status=status, limit=50)

    st.markdown(f"### 📋 {len(tasks)} Task(s)")

    # Add new task
    with st.expander("➕ Add New Task"):
        with st.form("new_task"):
            title = st.text_input("Task Title*")
            description = st.text_area("Description")

            col1, col2 = st.columns(2)
            with col1:
                project_new = st.selectbox("Project", ["System", "Penterra", "Genealogy"])
                priority_new = st.selectbox("Priority", ["Medium", "Low", "High", "Critical"])

            with col2:
                due_date = st.date_input("Due Date")
                tags = st.text_input("Tags (comma-separated)")

            if st.form_submit_button("Add Task"):
                if title:
                    new_task = Task(
                        title=title,
                        description=description,
                        project=project_new,
                        priority=priority_new,
                        due_date=due_date.isoformat() if due_date else None,
                        tags=tags
                    )
                    task_id = todo_mgr.add_task(new_task)
                    st.success(f"Task #{task_id} created!")
                    st.rerun()
                else:
                    st.error("Title is required!")

    # Display tasks
    for task in tasks:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                priority_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
                emoji = priority_emoji.get(task.priority, "⚪")

                st.markdown(f"{emoji} **{task.title}**")
                if task.description:
                    st.caption(task.description[:100] + "..." if len(task.description) > 100 else task.description)
                st.caption(f"Project: {task.project} | Status: {task.status}")

            with col2:
                st.metric("Score", f"{task.ai_score}/100")

            with col3:
                if task.status != "Done":
                    if st.button("✅ Complete", key=f"complete_{task.task_id}"):
                        todo_mgr.mark_complete(task.task_id)
                        st.success("Task completed!")
                        st.rerun()

            st.markdown("---")


def render_links_page():
    """Render the Apps & Links page."""
    st.markdown("## 🔗 Apps & Links Hub")

    links_mgr = st.session_state.links_manager

    # Workflow Groups Section
    st.markdown("### ⚡ Workflow Groups")

    cols = st.columns(4)
    for idx, group in enumerate(links_mgr.workflow_groups.values()):
        with cols[idx % 4]:
            if st.button(f"{group.icon} {group.name}", key=f"group_{group.group_id}", use_container_width=True):
                links_mgr.open_workflow_group(group.group_id)
                st.success(f"Launched {group.name}!")

    st.markdown("---")

    # Category tabs
    st.markdown("### 🔗 Links by Category")

    categories = links_mgr.get_all_categories()
    category_tabs = st.tabs(categories)

    for idx, category in enumerate(categories):
        with category_tabs[idx]:
            links = links_mgr.get_links_by_category(category)

            cols = st.columns(4)
            for link_idx, link in enumerate(links):
                with cols[link_idx % 4]:
                    if st.button(
                        f"{link.icon}\n{link.name}",
                        key=f"link_{link.link_id}",
                        use_container_width=True,
                        help=link.description
                    ):
                        links_mgr.open_link(link.link_id)
                        st.success(f"Opened {link.name}!")


def render_agents_page():
    """Render the Agents page."""
    st.markdown("## 🤖 AI Agent Console")

    agents_mgr = st.session_state.agents_manager

    # Display agents
    st.markdown("### Available Agents")

    cols = st.columns(4)
    for idx, agent in enumerate(agents_mgr.get_all_agents(active_only=True)):
        with cols[idx % 4]:
            st.markdown(f"""
            <div class="link-card">
                <h2>{agent.icon}</h2>
                <h4>{agent.name}</h4>
                <p><small>{agent.role}</small></p>
            </div>
            """, unsafe_allow_html=True)
            st.caption(agent.description)

    st.markdown("---")

    # Queue a task
    st.markdown("### 📝 Queue Task for Agent")

    with st.form("queue_agent_task"):
        col1, col2 = st.columns(2)

        with col1:
            agent_options = {agent.agent_id: f"{agent.icon} {agent.name}"
                           for agent in agents_mgr.get_all_agents(active_only=True)}
            selected_agent = st.selectbox("Select Agent", options=list(agent_options.keys()),
                                        format_func=lambda x: agent_options[x])

        with col2:
            priority = st.selectbox("Priority", ["Medium", "Low", "High", "Critical"])

        title = st.text_input("Task Title*")
        description = st.text_area("Task Description*")

        if st.form_submit_button("Queue Task"):
            if title and description and selected_agent:
                task_id = agents_mgr.queue_task(selected_agent, title, description, priority)
                st.success(f"Task #{task_id} queued for {agent_options[selected_agent]}!")
            else:
                st.error("Please fill all required fields!")

    st.markdown("---")

    # Show queued tasks
    st.markdown("### 📋 Queued Tasks")

    queued_tasks = agents_mgr.get_agent_tasks(status="Queued", limit=10)

    if queued_tasks:
        for task in queued_tasks:
            agent = agents_mgr.get_agent(task.agent_id)

            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**{task.title}** → {agent.icon} {agent.name}")
                st.caption(task.description)

            with col2:
                if st.button("▶️ Execute", key=f"exec_{task.task_id}"):
                    with st.spinner("Executing task..."):
                        result = agents_mgr.execute_task(task.task_id, use_llm=True)
                        if result['success']:
                            st.success("Task completed!")
                            with st.expander("View Result"):
                                st.text(result['result'])
                        else:
                            st.error(f"Error: {result.get('error')}")

            st.markdown("---")
    else:
        st.info("No queued tasks")


def render_ocr_page():
    """Render the Title & OCR page."""
    st.markdown("## 📄 Title & OCR Workflow")

    ocr = st.session_state.ocr_orchestrator

    # Scan for documents
    st.markdown("### 📂 Scanned Documents")

    if st.button("🔍 Scan for Documents"):
        with st.spinner("Scanning..."):
            documents = ocr.scan_for_documents()
            st.session_state.scanned_docs = documents

    if 'scanned_docs' in st.session_state:
        docs = st.session_state.scanned_docs
        st.info(f"Found {len(docs)} document(s)")

        if docs:
            # Show first 10
            for doc in docs[:10]:
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.write(f"📄 **{doc.file_name}**")
                    st.caption(f"Type: {doc.document_type} | Size: {doc.file_size:,} bytes")

                with col2:
                    st.caption(f"Modified: {doc.modified_date[:10]}")

                with col3:
                    if st.button("Process", key=f"proc_{doc.file_path}"):
                        st.info("Processing would happen here!")

                st.markdown("---")

    st.markdown("---")

    # Manual processing
    st.markdown("### ⚙️ Manual Processing")

    with st.form("manual_ocr"):
        file_path = st.text_input("Document Path")
        use_llm = st.checkbox("Use AI Enhancement", value=True)

        if st.form_submit_button("Run OCR"):
            if file_path:
                with st.spinner("Processing document..."):
                    result = ocr.process_document(file_path, use_llm)

                    if result['success']:
                        st.success("Document processed!")

                        with st.expander("View Extracted Data"):
                            st.json(result['extracted_data'])
                    else:
                        st.error(f"Error: {result.get('error')}")
            else:
                st.error("Please provide a file path!")


def render_deals_page():
    """Render the Money & Deals page."""
    st.markdown("## 💰 Money & Deals Engine")

    deals_engine = st.session_state.deals_engine

    # Statistics
    stats = deals_engine.get_statistics()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Deals", stats.get('total_deals', 0))

    with col2:
        total_value = stats.get('total_estimated_value', 0)
        st.metric("Total Value", f"${total_value:,.0f}")

    with col3:
        avg_score = stats.get('avg_deal_score', 0)
        st.metric("Avg Score", f"{avg_score:.0f}/100")

    st.markdown("---")

    # Add new deal
    with st.expander("➕ Add New Deal"):
        with st.form("new_deal"):
            title = st.text_input("Deal Title*")
            description = st.text_area("Description*")

            col1, col2 = st.columns(2)

            with col1:
                category = st.selectbox("Category",
                    ["Missing Owner", "Mineral Rights", "Real Estate"])
                estimated_value = st.number_input("Estimated Value ($)", min_value=0.0, step=1000.0)

            with col2:
                difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
                contact_name = st.text_input("Contact Name")

            if st.form_submit_button("Add Deal"):
                if title and description:
                    new_deal = Deal(
                        title=title,
                        description=description,
                        category=category,
                        estimated_value=estimated_value,
                        difficulty=difficulty,
                        contact_name=contact_name
                    )
                    new_deal.deal_score = deals_engine.calculate_deal_score(new_deal)
                    deal_id = deals_engine.add_deal(new_deal)
                    st.success(f"Deal #{deal_id} created with score {new_deal.deal_score}/100!")
                    st.rerun()
                else:
                    st.error("Title and description are required!")

    # Display deals
    st.markdown("### 🎯 High-Value Deals")

    deals = deals_engine.get_deals(status="Prospect", min_score=60, limit=20)

    for deal in deals:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{deal.title}** ({deal.category})")
                st.caption(deal.description[:100] + "..." if len(deal.description) > 100 else deal.description)
                if deal.contact_name:
                    st.caption(f"Contact: {deal.contact_name}")

            with col2:
                st.metric("Value", f"${deal.estimated_value:,.0f}")
                st.caption(f"Difficulty: {deal.difficulty}")

            with col3:
                st.metric("Score", f"{deal.deal_score}/100")

                if st.button("📧 Generate Package", key=f"gen_{deal.deal_id}"):
                    with st.spinner("Generating..."):
                        result = deals_engine.generate_contact_package(deal.deal_id)
                        if result['success']:
                            st.success("Package generated!")
                            st.info(f"Saved to: {result['email_path']}")
                        else:
                            st.error(f"Error: {result.get('error')}")

            st.markdown("---")


def render_settings_page():
    """Render the Settings page."""
    st.markdown("## ⚙️ Settings")

    config = st.session_state.config

    # Display current config
    st.markdown("### 📋 Current Configuration")

    with st.expander("View Full Configuration"):
        st.json(config.get_all())

    st.markdown("---")

    # Edit key settings
    st.markdown("### 🔧 Edit Settings")

    with st.form("edit_settings"):
        st.subheader("Paths")
        root_dir = st.text_input("Root Directory", value=config.get('paths.root_dir'))
        input_dir = st.text_input("Input Directory", value=config.get('paths.input_dir'))
        output_dir = st.text_input("Output Directory", value=config.get('paths.output_dir'))

        st.subheader("AI Settings")
        use_llm = st.checkbox("Enable LLM Router", value=config.get('ai.use_llm_router'))
        temperature = st.slider("Temperature", 0.0, 1.0, config.get('ai.temperature', 0.7))

        st.subheader("Features")
        enable_ocr = st.checkbox("Enable OCR", value=config.get('features.enable_ocr'))
        enable_deals = st.checkbox("Enable Deals Engine", value=config.get('features.enable_deals_engine'))
        enable_agents = st.checkbox("Enable Agents", value=config.get('features.enable_agents'))

        if st.form_submit_button("Save Settings"):
            config.set('paths.root_dir', root_dir)
            config.set('paths.input_dir', input_dir)
            config.set('paths.output_dir', output_dir)
            config.set('ai.use_llm_router', use_llm)
            config.set('ai.temperature', temperature)
            config.set('features.enable_ocr', enable_ocr)
            config.set('features.enable_deals_engine', enable_deals)
            config.set('features.enable_agents', enable_agents)

            st.success("Settings saved!")
            st.rerun()

    st.markdown("---")

    # System actions
    st.markdown("### 🔨 System Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Reload Config"):
            from command_center.config_databossx9 import reload_config
            reload_config()
            st.success("Config reloaded!")

    with col2:
        if st.button("📁 Ensure Directories"):
            config.ensure_directories()
            st.success("Directories verified!")

    with col3:
        if st.button("🎨 Generate Logo"):
            from command_center.logo_builder9 import LogoBuilder
            with st.spinner("Generating logo..."):
                builder = LogoBuilder()
                assets = builder.create_all_assets()
                st.success("Logo assets generated!")


def main():
    """Main application entry point."""
    # Initialize
    init_session_state()

    # Render header
    render_header()

    # Render sidebar and get selected page
    page = render_sidebar()

    # Render selected page
    if page == "🏠 Overview":
        render_overview_page()
    elif page == "✅ To Do":
        render_todo_page()
    elif page == "🔗 Apps & Links":
        render_links_page()
    elif page == "🤖 Agents":
        render_agents_page()
    elif page == "📄 Title & OCR":
        render_ocr_page()
    elif page == "💰 Money & Deals":
        render_deals_page()
    elif page == "⚙️ Settings":
        render_settings_page()


if __name__ == "__main__":
    main()
