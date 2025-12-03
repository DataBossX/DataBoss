# DataBossX Command Center v9.0 - Deployment Guide

## 🚀 Quick Start

The DataBossX Command Center is your central control panel for managing tasks, AI agents, documents, deals, and external tools. This guide will help you get it up and running.

---

## 📋 Prerequisites

### Required Software
- **Python 3.8+** (3.9 or higher recommended)
- **pip** (Python package manager)
- **Modern web browser** (Chrome, Firefox, Edge, or Safari)

### Recommended
- **Virtual environment** (venv or conda)
- **Git** (for version control)
- **Windows 10/11** (for .bat launcher) or **Linux/Mac** (for .sh launcher)

---

## 📦 Installation

### Step 1: Navigate to Your Installation Directory

**Windows:**
```cmd
cd I:\DataBossX_Final_Modular
```

**Linux/Mac:**
```bash
cd /path/to/DataBossX
```

### Step 2: Create a Virtual Environment (Recommended)

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies:**
- streamlit
- pillow

**Optional dependencies** (for full functionality):
- Any existing llm_router dependencies from your project

### Step 4: Verify Installation

```bash
python command_center/config_databossx9.py
```

You should see:
```
✓ Configuration is valid
Configuration saved to: config_databossx9.json
```

---

## 🎯 Launching the Command Center

### Method 1: Using the Launcher Scripts (Easiest)

**Windows:**
```cmd
databossx_launch9.bat
```

**Linux/Mac:**
```bash
./databossx_launch9.sh
```

The Command Center will automatically:
1. Activate the virtual environment (if present)
2. Check for dependencies
3. Launch the Streamlit dashboard
4. Open your browser to http://localhost:8501

### Method 2: Manual Launch

```bash
streamlit run databossx_dashboard9.py
```

### Method 3: From Python

```python
import subprocess
subprocess.run(["streamlit", "run", "databossx_dashboard9.py"])
```

---

## 🏗️ File Structure

```
DataBossX_Final_Modular/
├── databossx_dashboard9.py           # Main Streamlit dashboard
├── databossx_launch9.bat             # Windows launcher
├── databossx_launch9.sh              # Linux/Mac launcher
├── requirements.txt                   # Python dependencies
├── README_shortcut.txt               # Desktop shortcut guide
├── DEPLOYMENT_GUIDE.md               # This file
│
├── command_center/                   # Core modules
│   ├── config_databossx9.py          # Configuration manager
│   ├── logo_builder9.py              # Logo generator
│   ├── todo_manager9.py              # Task management
│   ├── links_manager9.py             # Apps & links hub
│   ├── agents_manager9.py            # AI agent console
│   ├── title_ocr_orchestrator9.py    # OCR workflows
│   ├── deals_engine9.py              # Money & deals
│   └── helper_suggestions9.py        # Helper system
│
├── assets/                           # Generated assets
│   ├── databossx_logo.png            # Main logo
│   ├── databossx_logo_small.png      # Small logo
│   ├── databossx_logo.ico            # Windows icon
│   └── favicon.ico                   # Browser favicon
│
├── input/                            # Input documents
├── output/                           # Output files
│   └── deals/                        # Generated deal packages
├── logs/                             # Log files
├── penterra_files/                   # Penterra documents
└── genealogy/                        # Genealogy files
```

---

## ⚙️ Configuration

### Main Configuration File: `config_databossx9.json`

This file is automatically created on first run. You can edit it directly or use the Settings page in the dashboard.

**Key configuration sections:**

1. **Paths** - Directory locations
2. **AI** - LLM integration settings
3. **UI** - Dashboard appearance
4. **Features** - Enable/disable features
5. **Performance** - Cache and optimization settings

### Links Configuration: `links_config9.json`

Pre-populated with 20+ essential tools:
- AI tools (ChatGPT, Claude, Gemini, DeepSeek, Perplexity)
- Communication (AOL, Gmail)
- Research tools (County records, Tax records, Genealogy sites)
- Development tools
- And more...

### Agents Configuration: `agents_config9.json`

Defines 7 AI agents with different roles:
- 👷 **Builder** - Software engineering
- 🔬 **Researcher** - Research and analysis
- 🧪 **Tester** - QA and testing
- 💰 **Money Maker** - Business development
- 📄 **Title OCR Agent** - Document processing
- 🎯 **Deal Finder** - Opportunity scouting
- 🎨 **Artist** - Creative design

---

## 🎨 Creating a Desktop Shortcut

See `README_shortcut.txt` for detailed instructions on creating a desktop shortcut with the custom DataBossX icon.

**Quick version (Windows):**
1. Right-click `databossx_launch9.bat` → Create shortcut
2. Right-click shortcut → Properties → Change Icon
3. Browse to `assets/databossx_logo.ico`
4. Move shortcut to Desktop

---

## 📱 Using the Command Center

### Overview Tab (🏠)
- View suggestions and alerts
- See your "Next Best Move" task
- Quick launch buttons for AI Stack and key features
- Dashboard statistics

### To Do Tab (✅)
- Manage tasks with filtering by project, priority, and status
- Add new tasks with descriptions, due dates, and tags
- AI-powered task scoring
- Mark tasks complete

### Apps & Links Tab (🔗)
- Quick access to 20+ external tools
- Workflow Groups for launching multiple related tools
- Launch AI Stack (all AI tools at once)
- Usage tracking

### Agents Tab (🤖)
- View all AI agents and their capabilities
- Queue tasks for agents to process
- Execute queued tasks
- View task results

### Title & OCR Tab (📄)
- Scan for PDF documents in input folders
- Run OCR processing on documents
- Extract structured data (Grantor, Grantee, Book/Page, Legal Description)
- Batch processing

### Money & Deals Tab (💰)
- Track business opportunities
- Add deals with estimated value and difficulty
- AI deal scoring (0-100)
- Generate contact packages (emails and letters)
- View high-value deals

### Settings Tab (⚙️)
- Edit configuration settings
- Manage paths and directories
- Toggle features on/off
- System actions (reload config, ensure directories, generate logo)

---

## 🔧 Customization

### Adding New Links

1. **Via Dashboard:**
   - Go to Settings → Edit the links_config9.json
   - Or use the Links Manager API

2. **Programmatically:**
   ```python
   from command_center.links_manager9 import LinksManager

   manager = LinksManager()
   # Add your custom links
   manager.save_config()
   ```

### Adding Custom Agents

Edit `agents_config9.json` or use the Agents Manager API:

```python
from command_center.agents_manager9 import AgentsManager, Agent

manager = AgentsManager()
custom_agent = Agent(
    agent_id="my_agent",
    name="My Custom Agent",
    role="Custom Role",
    description="What this agent does",
    icon="🌟",
    capabilities=["capability1", "capability2"],
    specialties=["specialty1", "specialty2"]
)
# Add and save
```

### Modifying the Dashboard

The dashboard is built with Streamlit. Edit `databossx_dashboard9.py` to:
- Add new tabs
- Modify layouts
- Add custom visualizations
- Integrate with other tools

---

## 🔌 Integration with Existing Systems

### LLM Router Integration

The Command Center is designed to work with your existing `llm_router` (if available):

1. Set `ai.use_llm_router` to `true` in config
2. Set `ai.llm_router_path` to your router module path
3. Agents and OCR features will use the router automatically

### Database Integration

The system uses SQLite databases:
- `databossx_tasks.db` - Task management
- `databossx_agents.db` - Agent tasks
- `databossx_deals.db` - Deals and opportunities

You can query these directly or use the manager APIs.

---

## 🐛 Troubleshooting

### Issue: "Module not found" errors
**Solution:** Install missing packages:
```bash
pip install streamlit pillow
```

### Issue: Dashboard doesn't load
**Solution:**
1. Check that port 8501 is not in use
2. Try a different port: `streamlit run databossx_dashboard9.py --server.port 8502`

### Issue: Logo not displaying
**Solution:** Regenerate assets:
```bash
python command_center/logo_builder9.py
```

### Issue: Configuration errors
**Solution:** Delete config files and regenerate:
```bash
rm config_databossx9.json links_config9.json agents_config9.json
python command_center/config_databossx9.py
python command_center/links_manager9.py
python command_center/agents_manager9.py
```

### Issue: Launcher script fails on Windows
**Solution:**
1. Check that the path in the .bat file matches your installation
2. Run as Administrator if needed
3. Ensure Python is in your PATH

### Issue: Permission denied on Linux/Mac
**Solution:**
```bash
chmod +x databossx_launch9.sh
```

---

## 📊 Performance Tips

1. **Enable Caching:** Set `performance.cache_enabled` to `true` in config
2. **Limit Batch Sizes:** Adjust `ocr.batch_size` for your system
3. **Use Virtual Environment:** Keeps dependencies isolated and fast
4. **Close Unused Tabs:** Browser tabs consume memory

---

## 🔒 Security Considerations

1. **Sensitive Data:** The system stores data in SQLite databases. Ensure these files are backed up and secured.
2. **API Keys:** If integrating with LLMs, store API keys in environment variables, not in config files.
3. **Network Access:** The dashboard runs on localhost by default. To access remotely, use:
   ```bash
   streamlit run databossx_dashboard9.py --server.address 0.0.0.0
   ```
   **Warning:** Only do this on trusted networks!

---

## 📚 Additional Resources

### Log Files
- **databossx_log9.log** - Application logs
- Check this file first when troubleshooting

### Documentation
- Streamlit docs: https://docs.streamlit.io
- Python docs: https://docs.python.org

### Support
- Check log files for errors
- Review configuration files
- Test individual modules independently

---

## 🚀 Advanced Usage

### Running Tests

Test individual components:

```bash
# Test configuration
python command_center/config_databossx9.py

# Test todo manager
python command_center/todo_manager9.py

# Test links manager
python command_center/links_manager9.py

# Test agents manager
python command_center/agents_manager9.py
```

### API Usage

All managers can be used as Python APIs:

```python
from command_center.todo_manager9 import TodoManager, Task
from command_center.deals_engine9 import DealsEngine, Deal
from command_center.agents_manager9 import AgentsManager

# Create a task
todo_mgr = TodoManager()
task = Task(title="My Task", project="System", priority="High")
task_id = todo_mgr.add_task(task)

# Create a deal
deals = DealsEngine()
deal = Deal(title="Big Opportunity", estimated_value=50000)
deal_id = deals.add_deal(deal)

# Queue agent task
agents = AgentsManager()
task_id = agents.queue_task("researcher", "Research topic", "Details here")
```

---

## 🎉 You're Ready!

The DataBossX Command Center is now fully set up and ready to use. Launch it with the launcher script and explore all the features!

**Quick Launch:**
```bash
databossx_launch9.bat    # Windows
./databossx_launch9.sh   # Linux/Mac
```

**Next Steps:**
1. Create a desktop shortcut (see README_shortcut.txt)
2. Customize your links and agents
3. Start adding tasks and deals
4. Launch your AI Stack!

---

**Version:** 9.0
**Last Updated:** 2025-12-03
**Author:** DataBossX Team

For questions or issues, check the log files and configuration settings first!
