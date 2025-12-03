#!/bin/bash
# DataBossX Command Center Launcher (Linux/Mac)
# This script launches the Streamlit dashboard

echo "================================================"
echo "  DataBossX Command Center Launcher v9.0"
echo "================================================"
echo ""

# Navigate to the DataBossX root directory
# Adjust the path below if your installation is elsewhere
cd "$(dirname "$0")"
echo "Current directory: $(pwd)"
echo ""

# Check if we're in the right directory
if [ ! -f "databossx_dashboard9.py" ]; then
    echo "ERROR: Cannot find databossx_dashboard9.py"
    echo "Please ensure you're in the correct directory."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Activate the Python virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "WARNING: No virtual environment found."
    echo "Using system Python..."
fi
echo ""

# Check if Streamlit is installed
python3 -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Streamlit is not installed!"
    echo ""
    echo "Installing required packages..."
    pip install streamlit pillow
    echo ""
fi

# Launch the dashboard
echo "Launching DataBossX Command Center..."
echo ""
echo "================================================"
echo "  Dashboard will open in your browser"
echo "  Press Ctrl+C to stop the server"
echo "================================================"
echo ""

streamlit run databossx_dashboard9.py

# If streamlit exits, pause so user can see any errors
echo ""
echo "================================================"
echo "  Dashboard stopped"
echo "================================================"
echo ""
read -p "Press Enter to exit..."
