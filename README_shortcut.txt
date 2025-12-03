================================================================================
  DataBossX Command Center - Desktop Shortcut Setup Guide
================================================================================

This guide explains how to create a desktop shortcut with a custom icon for
the DataBossX Command Center.

================================================================================
  WINDOWS INSTRUCTIONS
================================================================================

1. LOCATE THE LAUNCHER FILE
   - Navigate to: I:\DataBossX_Final_Modular
   - Find: databossx_launch9.bat

2. CREATE A SHORTCUT
   - Right-click on databossx_launch9.bat
   - Select "Create shortcut"
   - A new shortcut will appear in the same folder

3. SET THE CUSTOM ICON
   - Right-click on the shortcut
   - Select "Properties"
   - Click the "Change Icon..." button
   - Click "Browse..." and navigate to:
     I:\DataBossX_Final_Modular\assets\databossx_logo.ico
   - Select the logo and click "OK"
   - Click "OK" again to close Properties

4. RENAME THE SHORTCUT (Optional)
   - Right-click the shortcut
   - Select "Rename"
   - Change name to: "DataBossX Command Center"

5. MOVE TO DESKTOP
   - Drag the shortcut to your Desktop
   - Or: Right-click > "Send to" > "Desktop (create shortcut)"

6. LAUNCH!
   - Double-click the desktop shortcut
   - The Command Center will launch in your default browser

================================================================================
  LINUX/MAC INSTRUCTIONS
================================================================================

1. MAKE THE SCRIPT EXECUTABLE
   cd /path/to/DataBossX
   chmod +x databossx_launch9.sh

2. CREATE A DESKTOP ENTRY (Linux)
   Create file: ~/.local/share/applications/databossx.desktop

   Contents:
   [Desktop Entry]
   Type=Application
   Name=DataBossX Command Center
   Comment=Launch DataBossX Control Panel
   Exec=/path/to/DataBossX/databossx_launch9.sh
   Icon=/path/to/DataBossX/assets/databossx_logo.png
   Terminal=true
   Categories=Development;Office;

3. MAKE IT EXECUTABLE
   chmod +x ~/.local/share/applications/databossx.desktop

4. FOR MAC (Create an App with Automator)
   - Open Automator
   - Choose "Application"
   - Add "Run Shell Script" action
   - Paste: cd /path/to/DataBossX && ./databossx_launch9.sh
   - Save as "DataBossX.app"
   - Right-click app > Get Info > drag logo to icon area

================================================================================
  TROUBLESHOOTING
================================================================================

PROBLEM: "File not found" error
SOLUTION: Check that the path in the launcher script matches your actual
          installation directory. Edit the .bat or .sh file if needed.

PROBLEM: "Streamlit not found" error
SOLUTION: The launcher will automatically try to install Streamlit.
          If this fails, manually run: pip install streamlit pillow

PROBLEM: Icon doesn't appear
SOLUTION: Make sure you've run the logo builder first:
          python command_center/logo_builder9.py

PROBLEM: Browser doesn't open automatically
SOLUTION: Wait a few seconds, then manually open your browser and go to:
          http://localhost:8501

================================================================================
  ADDITIONAL TIPS
================================================================================

1. KEYBOARD SHORTCUTS
   - You can assign a keyboard shortcut to the Windows shortcut
   - Right-click shortcut > Properties > Shortcut key

2. TASKBAR PINNING
   - Drag the shortcut to the Windows taskbar for quick access

3. STARTUP LAUNCH
   - Copy shortcut to: C:\Users\YourName\AppData\Roaming\Microsoft\Windows
     \Start Menu\Programs\Startup
   - Command Center will launch automatically on Windows startup

4. MULTIPLE MONITORS
   - The dashboard will remember which monitor you use
   - Just drag the browser window to your preferred screen

================================================================================
  CONTACT & SUPPORT
================================================================================

For issues or questions about the Command Center:
- Check the log file: databossx_log9.log
- Review configuration: config_databossx9.json
- Regenerate assets: python command_center/logo_builder9.py

Version: 9.0
Last Updated: 2025-12-03

================================================================================
