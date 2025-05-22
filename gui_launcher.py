import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import os
import json
import webbrowser
import threading
import time
import shutil

# Try to import extractor.py from same directory
try:
    from extractor import run_extraction
except ImportError:
    raise RuntimeError("Could not find extractor.py. Make sure it's in the same directory.")

def setup_system_paths():
    """Setup system paths for DataBoss"""
    import sys
    import os
    
    if os.name == 'nt' and os.path.exists("D:/DataBoss/DataBossX_Final_Modular/"):
        sys.path.insert(0, "D:/DataBoss/DataBossX_Final_Modular/")
        return True
    return False

setup_system_paths()

# App Constants
WINDOW_TITLE = "📄 DataBoss Legal Document Processor"
WINDOW_SIZE = "900x600"
SUPPORTED_TYPES = [("PDF Files", "*.pdf")]
INPUT_DIR = Path("input_pdfs")
OUTPUT_DIR = Path("output_results")

# Ensure required directories exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class DataBossGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(True, True)

        self.current_file = None
        self.current_result = None

        self.create_widgets()
        self.setup_drag_drop()

    def create_widgets(self):
        """Build the main UI components"""
        # File selection
        self.file_frame = tk.Frame(self.root)
        self.file_frame.pack(pady=10, fill=tk.X, padx=10)

        self.select_button = tk.Button(self.file_frame, text="📁 Select PDF(s)", command=self.select_files)
        self.select_button.pack(side=tk.LEFT)

        self.status_label = tk.Label(self.file_frame, text="No file selected", width=50, anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # JSON Output
        self.output_frame = tk.Frame(self.root)
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(self.output_frame, wrap=tk.WORD, font=("Courier New", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        self.process_button = tk.Button(
            self.button_frame,
            text="⚙️ Process Document",
            command=self.start_processing,
            width=20,
            bg="#4CAF50",
            fg="white"
        )
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.download_button = tk.Button(
            self.button_frame,
            text="⬇️ Download Excel",
            command=self.download_excel,
            width=20,
            state=tk.DISABLED,
            bg="#2196F3",
            fg="white"
        )
        self.download_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(
            self.button_frame,
            text="🗑️ Clear",
            command=self.clear_output,
            width=10,
            bg="#f44336",
            fg="white"
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        self.voice_button = tk.Button(
            self.button_frame,
            text="🎤 Voice",
            command=self.toggle_voice,
            width=10,
            bg="#9c27b0",
            fg="white"
        )
        self.voice_button.pack(side=tk.LEFT, padx=5)

        # Status Bar
        self.status_bar = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_drag_drop(self):
        """Enable drag-and-drop support for file uploads"""

        def on_drop(event):
            files = self.root.tk.splitlist(event.data)
            self.handle_files(files)

        self.root.drop_target_register("DND_Files")
        self.root.dnd_bind("<<Drop>>", on_drop)

    def select_files(self):
        """Open file dialog to select PDFs"""
        files = filedialog.askopenfilenames(filetypes=SUPPORTED_TYPES)
        if files:
            self.handle_files(files)

    def handle_files(self, files):
        """Handle uploaded files (drag or select)"""
        self.clear_output()
        self.status("Processing files...")

        for file in files:
            src = Path(file)
            dst = INPUT_DIR / src.name
            try:
                shutil.copy2(src, dst)
                self.status(f"Saved: {src.name}")
                self.current_file = dst
            except Exception as e:
                messagebox.showerror("File Error", f"Could not copy {src.name}: {e}")
                continue

        if not self.current_file:
            return

        self.status("Ready to process")
        self.status_label.config(text=f"Selected: {self.current_file.name}")

    def start_processing(self):
        """Start processing in a separate thread to keep GUI responsive"""
        if not self.current_file:
            messagebox.showwarning("No File", "Please select a PDF first.")
            return

        self.status("Processing document...")
        self.process_button.config(state=tk.DISABLED)
        self.download_button.config(state=tk.DISABLED)
        self.output_text.delete(1.0, tk.END)

        threading.Thread(
            target=self.run_extraction,
            daemon=True
        ).start()

    def run_extraction(self):
        """Run the backend extraction logic"""
        try:
            result = run_extraction(str(self.current_file), str(INPUT_DIR), str(OUTPUT_DIR))
            self.current_result = result
            self.status("✅ Extraction complete")
            self.download_button.config(state=tk.NORMAL)
            self.display_json(result)
        except Exception as e:
            self.status("❌ Error during extraction")
            messagebox.showerror("Processing Error", str(e))
        finally:
            self.process_button.config(state=tk.NORMAL)

    def display_json(self, result):
        """Display structured JSON output in scrollable text box"""
        try:
            with open(result["output_files"]["json"], "r", encoding="utf-8") as f:
                json_data = json.load(f)
            self.output_text.insert(tk.END, json.dumps(json_data, indent=2))
        except Exception as e:
            self.output_text.insert(tk.END, f"Error loading JSON: {str(e)}")

    def download_excel(self):
        """Open Excel file or show error"""
        if not self.current_result:
            return

        excel_path = self.current_result.get("output_files", {}).get("excel")
        if not excel_path or not os.path.exists(excel_path):
            messagebox.showerror("Not Found", "Excel file not found. Please re-process the document.")
            return

        try:
            if os.name == "nt":  # Windows
                os.startfile(excel_path)
            elif os.name == "posix":  # macOS/Linux
                webbrowser.open(f"file://{excel_path}")
        except Exception as e:
            messagebox.showerror("Open Failed", f"Could not open Excel file: {str(e)}")

    def clear_output(self):
        """Clear the JSON display and reset buttons"""
        self.current_file = None
        self.current_result = None
        self.output_text.delete(1.0, tk.END)
        self.status("Ready")
        self.status_label.config(text="No file selected")
        self.download_button.config(state=tk.DISABLED)

    def toggle_voice(self):
        """Toggle voice recognition on/off"""
        if not hasattr(self, 'voice_automation'):
            self.voice_automation = VoiceAutomation(self)
        
        self.voice_automation.toggle_listening()
        
    def status(self, message):
        """Update the status bar"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()


class VoiceAutomation:
    """Voice automation for the DataBoss application"""
    def __init__(self, app_instance):
        self.app = app_instance
        self.is_listening = False
        self.thread = None
    
    def toggle_listening(self):
        """Toggle voice recognition on/off"""
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        """Start voice recognition in a separate thread"""
        try:
            import speech_recognition as sr
            self.is_listening = True
            self.thread = threading.Thread(target=self._listen_loop)
            self.thread.daemon = True
            self.thread.start()
            self.app.status("🎤 Voice recognition active")
        except ImportError:
            messagebox.showwarning("Voice Recognition", 
                                  "Speech recognition package not installed.\n"
                                  "Install with: pip install SpeechRecognition")
    
    def stop_listening(self):
        """Stop voice recognition"""
        self.is_listening = False
        self.app.status("Voice recognition stopped")
    
    def _listen_loop(self):
        """Background listening loop"""
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        while self.is_listening:
            try:
                with sr.Microphone() as source:
                    self.app.status("Listening...")
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    
                text = recognizer.recognize_google(audio)
                self.app.status(f"Recognized: {text}")
                
                if "process" in text.lower() or "analyze" in text.lower():
                    self.app.start_processing()
                elif "clear" in text.lower():
                    self.app.clear_output()
                elif "download" in text.lower() or "excel" in text.lower():
                    self.app.download_excel()
                elif "stop" in text.lower() or "exit" in text.lower():
                    self.stop_listening()
                    
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                self.app.status(f"Voice recognition error: {str(e)}")
                time.sleep(2)


if __name__ == "__main__":
    root = tk.Tk()
    app = DataBossGUI(root)
    root.mainloop()
