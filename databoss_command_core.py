"""
Command core for DataBoss
Handles core system functions and launches components
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import tkinter as tk
from tkinter import messagebox
import webbrowser

logger = logging.getLogger("databoss.command_core")
logging.basicConfig(level=logging.INFO)

class CommandCore:
    def __init__(self):
        self.processes = {}
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load system configuration"""
        config_path = "databoss_config.json"
        default_config = {
            "streamlit_port": 8501,
            "fastapi_port": 8000,
            "input_dir": "input_pdfs",
            "output_dir": "output_results",
            "enable_voice": True,
            "theme": "neon_blue"
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
            else:
                with open(config_path, "w") as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}", exc_info=True)
            return default_config
            
    def save_config(self) -> bool:
        """Save current configuration"""
        try:
            with open("databoss_config.json", "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {str(e)}", exc_info=True)
            return False
            
    def launch_streamlit(self) -> bool:
        """Launch Streamlit dashboard"""
        try:
            if "streamlit" in self.processes and self.processes["streamlit"].poll() is None:
                logger.info("Streamlit is already running")
                return True
                
            cmd = [sys.executable, "-m", "streamlit", "run", "app.py", 
                   "--server.port", str(self.config["streamlit_port"])]
            self.processes["streamlit"] = subprocess.Popen(cmd)
            
            if self.config.get("enable_voice", True):
                self.play_voice_feedback("Welcome Commander. Dashboard ready.")
                
            logger.info(f"Streamlit launched on port {self.config['streamlit_port']}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch Streamlit: {str(e)}", exc_info=True)
            return False
            
    def play_voice_feedback(self, message: str) -> None:
        """Play voice feedback message"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(message)
            engine.runAndWait()
        except ImportError:
            logger.warning("pyttsx3 not installed, voice feedback disabled")
        except Exception as e:
            logger.error(f"Voice feedback error: {str(e)}")
            
    def shutdown(self) -> None:
        """Shutdown all running processes"""
        for name, process in self.processes.items():
            if process.poll() is None:
                logger.info(f"Terminating {name} process")
                process.terminate()
                
        time.sleep(1)
        
        for name, process in self.processes.items():
            if process.poll() is None:
                logger.warning(f"Force killing {name} process")
                process.kill()
