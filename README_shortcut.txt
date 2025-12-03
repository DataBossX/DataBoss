==========================================
DataBossX Command Center v9
Desktop Shortcut Setup Instructions
==========================================

STEP 1: Locate the Launcher
----------------------------
The launcher file is located at:
    I:\DataBossX_Final_Modular\databossx_launch9.bat

(Or wherever you installed DataBossX)


STEP 2: Create Desktop Shortcut
--------------------------------
1. Right-click on databossx_launch9.bat
2. Select "Create shortcut"
3. Drag the shortcut to your Desktop
4. Rename the shortcut to "DataBossX Command Center" (optional)


STEP 3: Customize the Shortcut Icon (Optional)
-----------------------------------------------
1. Right-click on the shortcut on your Desktop
2. Select "Properties"
3. Click the "Change Icon..." button
4. Click "Browse..."
5. Navigate to: I:\DataBossX_Final_Modular\assets\databossx_logo.ico
6. Select the icon and click "OK"
7. Click "Apply" and "OK"


STEP 4: Test the Shortcut
--------------------------
Double-click the shortcut to launch DataBossX Command Center.
The dashboard will open in your default web browser.


TROUBLESHOOTING:
----------------

Problem: "Python not found" error
Solution: Install Python 3.8+ from https://python.org
         Make sure to check "Add Python to PATH" during installation

Problem: "Streamlit not found" error
Solution: The launcher will auto-install Streamlit on first run
         Or manually run: pip install streamlit pandas pillow

Problem: Browser doesn't open automatically
Solution: Manually navigate to: http://localhost:8501

Problem: Port already in use
Solution: Close any existing Streamlit instances
         Or edit the batch file to use a different port


ADVANCED: Pin to Taskbar
-------------------------
1. Create the desktop shortcut as described above
2. Drag the shortcut to your Windows Taskbar
3. Right-click the taskbar icon > Properties to customize


ADVANCED: Start with Windows
-----------------------------
1. Press Win+R
2. Type: shell:startup
3. Copy your DataBossX shortcut to this folder
4. DataBossX will start automatically when Windows starts


FOLDER STRUCTURE:
-----------------
DataBossX_Final_Modular/
├── databossx_dashboard9.py     (Main dashboard)
├── databossx_launch9.bat        (Launcher script)
├── config/                      (Configuration files)
├── assets/                      (Logo and icons)
├── input/                       (Documents to process)
├── output/                      (Processed output)
│   └── deals/                   (Generated deal packages)
└── penterra_docs/              (Penterra documents)


ENVIRONMENT VARIABLES (Optional):
---------------------------------
For full functionality, create a .env file with:

OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here

These enable AI agent processing.


SUPPORT:
--------
For issues or questions, check the logs at:
    databossx_log9.log


==========================================
Thank you for using DataBossX!
==========================================
