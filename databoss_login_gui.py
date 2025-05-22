"""
Login GUI for DataBoss
Provides login interface and redirects to dashboard
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pathlib import Path
from typing import Callable, Optional
import webbrowser

from databoss_login import LoginManager
from databoss_command_core import CommandCore

class LoginGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DataBoss Command Center - Login")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        self.bg_color = "#121212"
        self.text_color = "#FFFFFF"
        self.accent_color = "#0077FF"  # Neon blue
        self.root.configure(bg=self.bg_color)
        
        self.login_manager = LoginManager()
        self.command_core = CommandCore()
        
        self.current_session = None
        self.logged_in_user = None
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create login screen widgets"""
        header_frame = tk.Frame(self.root, bg=self.bg_color)
        header_frame.pack(pady=30)
        
        logo_label = tk.Label(header_frame, 
                             text="⚡ DATABOSS ⚡", 
                             font=("Arial", 24, "bold"),
                             fg=self.accent_color,
                             bg=self.bg_color)
        logo_label.pack()
        
        subtitle = tk.Label(header_frame,
                           text="COMMAND CENTER",
                           font=("Arial", 12),
                           fg=self.text_color,
                           bg=self.bg_color)
        subtitle.pack(pady=5)
        
        form_frame = tk.Frame(self.root, bg=self.bg_color)
        form_frame.pack(pady=20)
        
        username_label = tk.Label(form_frame, 
                                 text="USERNAME:",
                                 font=("Arial", 10, "bold"),
                                 fg=self.text_color,
                                 bg=self.bg_color)
        username_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.username_entry = tk.Entry(form_frame, 
                                     width=30,
                                     font=("Arial", 12),
                                     bg="#1E1E1E",
                                     fg=self.text_color,
                                     insertbackground=self.text_color)
        self.username_entry.grid(row=1, column=0, pady=(0, 15))
        
        password_label = tk.Label(form_frame, 
                                 text="PASSWORD:",
                                 font=("Arial", 10, "bold"),
                                 fg=self.text_color,
                                 bg=self.bg_color)
        password_label.grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        
        self.password_entry = tk.Entry(form_frame, 
                                     width=30,
                                     font=("Arial", 12),
                                     show="•",
                                     bg="#1E1E1E",
                                     fg=self.text_color,
                                     insertbackground=self.text_color)
        self.password_entry.grid(row=3, column=0, pady=(0, 20))
        
        self.login_button = tk.Button(form_frame,
                                    text="LOGIN",
                                    font=("Arial", 12, "bold"),
                                    bg=self.accent_color,
                                    fg=self.text_color,
                                    activebackground="#005BB5",
                                    activeforeground=self.text_color,
                                    width=20,
                                    command=self.login)
        self.login_button.grid(row=4, column=0, pady=10)
        
        self.status_label = tk.Label(self.root,
                                   text="Enter credentials to continue",
                                   font=("Arial", 10),
                                   fg="#888888",
                                   bg=self.bg_color)
        self.status_label.pack(pady=10)
        
        version_label = tk.Label(self.root,
                               text="DataBoss v1.0.0",
                               font=("Arial", 8),
                               fg="#555555",
                               bg=self.bg_color)
        version_label.pack(side=tk.BOTTOM, pady=10)
        
    def login(self):
        """Handle login button click"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            self.status_label.config(text="Please enter both username and password", fg="#FF5555")
            return
            
        self.login_button.config(state=tk.DISABLED)
        self.status_label.config(text="Authenticating...", fg="#888888")
        self.root.update()
        
        session_id = self.login_manager.login(username, password)
        
        if session_id:
            self.current_session = session_id
            self.logged_in_user = username
            self.status_label.config(text="Login successful! Launching dashboard...", fg="#00AA00")
            
            self.root.after(1000, self.launch_dashboard)
        else:
            self.login_button.config(state=tk.NORMAL)
            self.status_label.config(text="Invalid username or password", fg="#FF5555")
            
    def launch_dashboard(self):
        """Launch the main dashboard after successful login"""
        if self.command_core.launch_streamlit():
            webbrowser.open(f"http://localhost:{self.command_core.config['streamlit_port']}")
            
            self.root.iconify()
