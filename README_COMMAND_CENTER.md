# DataBossX Command Center v9

**Production-Grade Streamlit Control Panel for DataBossX Ecosystem**

---

## 🚀 Overview

The DataBossX Command Center is a comprehensive, local Streamlit-based control panel that serves as the central operating system for all DataBossX operations. It integrates task management, AI agent orchestration, document processing, deal tracking, and workflow automation into a unified, dark-mode interface.

## ✨ Key Features

### 1. **Overview Dashboard**
- Real-time system status
- AI-powered "Next Best Move" suggestions
- Quick action buttons for common tasks
- System health monitoring

### 2. **Task Manager**
- SQLite-based task tracking
- AI scoring for priority ranking
- Project-based organization (Penterra, Genealogy, System)
- Overdue and blocked task detection

### 3. **Apps & Links Hub**
- 20+ pre-configured essential tools
- One-click "Launch AI Stack" (ChatGPT, Claude, Gemini, DeepSeek, Perplexity)
- Workflow groups for common operations
- Usage tracking and smart suggestions

### 4. **Agent Console**
- 7 specialized AI agents:
  - **Builder**: Code development
  - **Researcher**: Information gathering
  - **Tester**: QA and debugging
  - **Money Maker**: Business opportunities
  - **Title OCR Agent**: Document processing
  - **Deal Finder**: Opportunity discovery
  - **Artist**: UI/UX and design
- Task queuing and processing
- Performance metrics

### 5. **Title & OCR Workflow**
- Auto-scan input folders for documents
- OCR processing with confidence scoring
- Structured data extraction (Grantor, Grantee, Book/Page, etc.)
- OCR tournament for best results

### 6. **Money & Deals Engine**
- Deal tracking with AI scoring (0-100)
- Missing owner opportunities
- Mineral rights and real estate deals
- Auto-generate contact packages (email + letter)
- Pipeline value tracking

### 7. **Settings**
- Comprehensive configuration management
- Path settings
- UI preferences
- Export/import configuration

---

## 📁 File Structure

```
DataBossX/
├── databossx_dashboard9.py          # Main Streamlit dashboard
├── databossx_launch9.bat            # Windows launcher script
├── config_databossx9.py             # Configuration manager
├── todo_manager9.py                 # Task orchestrator
├── links_manager9.py                # Links & workflow manager
├── agents_manager9.py               # AI agent console
├── title_ocr_orchestrator9.py       # Document processing
├── deals_engine9.py                 # Deals tracker
├── helper_suggestions9.py           # AI helper system
├── logo_builder9.py                 # Logo generator
├── config/                          # Configuration files
│   ├── databossx_settings9.json
│   ├── links_config9.json
│   └── agents_config9.json
├── assets/                          # Logo and icons
│   ├── databossx_logo.png
│   └── databossx_logo.ico
├── input/                           # Documents to process
├── output/                          # Processed output
│   └── deals/                       # Generated deal packages
├── penterra_docs/                   # Penterra documents
├── databossx.db                     # Main SQLite database
├── databossx_tasks.db               # Tasks database
└── databossx_log9.log               # System logs
```

---

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- Windows 10/11 (for .bat launcher) or adapt for Linux/Mac

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Generate Logo Assets
```bash
python logo_builder9.py
```

### Step 3: Launch Dashboard

**On Windows:**
```bash
databossx_launch9.bat
```

**On Linux/Mac:**
```bash
streamlit run databossx_dashboard9.py
```

The dashboard will open at: http://localhost:8501

---

## 🔧 Configuration

### API Keys (Optional)

For full AI agent functionality, create a `.env` file:

```env
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
```

### Customizing Settings

All settings can be configured via:
1. **Settings Tab** in the dashboard
2. Direct editing of `config/databossx_settings9.json`
3. Programmatic access via `config_databossx9.get_config()`

---

## 💡 Usage Guide

### Quick Start Workflow

1. **Launch the Dashboard**
   - Double-click `databossx_launch9.bat` (or use the desktop shortcut)

2. **Check Overview**
   - View "Next Best Move" for AI-suggested priorities
   - Click "Launch AI Stack" to open all AI tools

3. **Manage Tasks**
   - Navigate to "To Do" tab
   - Add new tasks or update existing ones
   - Filter by Project, Status, or Priority

4. **Process Documents**
   - Go to "Title & OCR" tab
   - Place PDFs in `input/` or `penterra_docs/`
   - Click "Scan for Documents"
   - View extraction results

5. **Track Deals**
   - Open "Money & Deals" tab
   - Review top deals by AI score
   - Generate contact packages

6. **Use AI Agents**
   - Go to "Agents" tab
   - Select an agent
   - Queue a task
   - View results

### Common Workflows

#### Missing Owner Research
```
1. Apps & Links → Launch "Missing Owner Workflow"
   Opens: MOEA + County Records + ShareFile + FamilySearch
2. Research using opened tools
3. Money & Deals → Add new deal
4. Generate contact package
```

#### Document Processing
```
1. Place documents in input/ folder
2. Title & OCR → Scan for Documents
3. Review extraction results
4. Export structured data
```

#### AI-Assisted Task Prioritization
```
1. To Do → View all tasks
2. System auto-calculates AI scores
3. Overview → Check "Next Best Move"
4. Start highest-priority task
```

---

## 🎯 Module Documentation

### config_databossx9.py
**Purpose**: Centralized configuration management
**Key Functions**:
- `get_config()`: Get singleton config instance
- `get(section, key)`: Retrieve setting
- `set(section, key, value)`: Update setting
- `save_config()`: Persist changes

### todo_manager9.py
**Purpose**: Task tracking with AI scoring
**Key Functions**:
- `add_task()`: Create new task
- `get_tasks()`: Retrieve filtered tasks
- `calculate_ai_score()`: Score tasks 0-100
- `get_next_best_move()`: AI-suggested priority

### links_manager9.py
**Purpose**: Link and workflow management
**Key Functions**:
- `open_link(link_id)`: Open URL in browser
- `open_workflow_group(group_id)`: Launch workflow
- `get_most_used_links()`: Usage analytics

### agents_manager9.py
**Purpose**: AI agent orchestration
**Key Functions**:
- `queue_task()`: Queue agent task
- `process_task()`: Execute with LLM
- `get_agent_stats()`: Performance metrics

### title_ocr_orchestrator9.py
**Purpose**: Document processing
**Key Functions**:
- `scan_for_documents()`: Find PDFs
- `extract_title_data()`: Parse title info
- `run_ocr_tournament()`: Multi-engine OCR

### deals_engine9.py
**Purpose**: Deal tracking and scoring
**Key Functions**:
- `add_deal()`: Create new opportunity
- `calculate_deal_score()`: Score 0-100
- `generate_contact_package()`: Email + letter

### helper_suggestions9.py
**Purpose**: Intelligent suggestions
**Key Functions**:
- `get_all_suggestions()`: System tips
- `get_next_best_move()`: Top action
- `get_daily_summary()`: System overview

---

## 📊 Database Schema

### Tasks Database (`databossx_tasks.db`)

**tasks table**:
- id, title, description, project
- priority, status, assigned_agent
- due_date, created_at, updated_at
- ai_score, notes

**task_history table**:
- Audit trail for task changes

### Main Database (`databossx.db`)

**deals table**:
- id, deal_type, title, description
- prospect info (name, address, phone, email)
- property_address, county, state
- estimated_value, difficulty_level, deal_score
- status, priority, created_at, updated_at

**agent_tasks table**:
- Agent task queue and results

**documents, ocr_results, llm_analysis tables**:
- From existing backend integration

---

## 🔒 Security Notes

- All data stored locally in SQLite databases
- No external data transmission (except API calls with your keys)
- Logs stored in `databossx_log9.log`
- Configuration in plain JSON (encrypt sensitive data if needed)

---

## 🐛 Troubleshooting

### Dashboard won't start
```bash
# Check Python version
python --version  # Should be 3.8+

# Install/reinstall Streamlit
pip install --upgrade streamlit

# Check for port conflicts
# Streamlit runs on port 8501 by default
```

### Logo not displaying
```bash
# Regenerate logo assets
python logo_builder9.py

# Check assets/ folder exists
```

### Tasks not saving
```bash
# Check database file permissions
# Ensure databossx_tasks.db is writable
```

### AI agents not working
```bash
# Check .env file exists with API keys
# Verify API key validity
# Check databossx_log9.log for errors
```

---

## 🚀 Future Enhancements

- [ ] Real-time notifications
- [ ] Mobile-responsive UI
- [ ] Multi-user support
- [ ] Advanced analytics dashboard
- [ ] Integration with external calendars
- [ ] Voice command support
- [ ] Advanced AI reasoning for deals
- [ ] Automated follow-up scheduling

---

## 📝 Changelog

### Version 9.0 (Current)
- Initial Command Center release
- Full Streamlit dashboard
- 7 specialized AI agents
- AI-powered task prioritization
- Deal scoring engine
- OCR workflow orchestration
- Workflow automation

---

## 📄 License

Proprietary - DataBossX Internal Use Only

---

## 👤 Author

**Rodney ("DataBoss")**
DataBossX Ecosystem

---

## 🙏 Acknowledgments

- Built with Streamlit
- Powered by OpenAI, Anthropic, and Google AI
- OCR support via Tesseract and PaddleOCR

---

**For questions or support, check the logs at `databossx_log9.log`**
