import tkinter as tk
from tkinter import filedialog, scrolledtext
import xml.etree.ElementTree as ET
import pathlib
import shutil
import hashlib
import sys
from typing import Optional

# --- Configuration & Constants ---
POLL_INTERVAL_MS = 800
ROOT_TAG = "changes"

class ConsoleColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    @staticmethod
    def log(type_: str, message: str):
        color = ConsoleColors.OKBLUE
        if type_ == "SUCCESS": color = ConsoleColors.OKGREEN
        elif type_ == "ERROR": color = ConsoleColors.FAIL
        elif type_ == "WARN": color = ConsoleColors.WARNING
        print(f"{color}[{type_}] {message}{ConsoleColors.ENDC}")

class GeminiAutomator:
    def __init__(self):
        # Initialize as None, but enforce assignment before logic loop
        self.root_dir: Optional[pathlib.Path] = None
        self.last_hash: Optional[str] = None
        
        self.window = tk.Tk()
        self.setup_gui()
        
        # Blocking call to ensure root_dir is set
        self.select_root_directory()
        
        # Start the dialectic loop
        self.check_clipboard()
        self.window.mainloop()

    def setup_gui(self):
        self.window.title("Gemini XML Automator (Zero-Trust)")
        self.window.geometry("600x400")
        self.status_label = tk.Label(self.window, text="Initializing...", font=("Consolas", 10))
        self.status_label.pack(pady=5)
        
        self.log_box = scrolledtext.ScrolledText(self.window, height=20, state='disabled', font=("Consolas", 9))
        self.log_box.pack(fill='both', expand=True, padx=5, pady=5)

    def log_gui(self, message: str):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def select_root_directory(self):
        ConsoleColors.log("INFO", "Waiting for user to select root directory...")
        selected = filedialog.askdirectory(title="Select Project Root Folder")
        
        if not selected:
            ConsoleColors.log("ERROR", "No folder selected. Exiting.")
            sys.exit(1)
            
        self.root_dir = pathlib.Path(selected).resolve()
        
        title = f"Watching: {self.root_dir}"
        self.window.title(title)
        self.status_label.config(text=title)
        ConsoleColors.log("SUCCESS", f"Root locked to: {self.root_dir}")
        self.log_gui(f"Root locked: {self.root_dir}")

    def safe_path(self, user_path: str) -> pathlib.Path:
        """
        SECURITY CRITICAL: Enforce path confinement.
        """
        # FIX 1: Explicit check to satisfy "Operator '/' not supported for None"
        if self.root_dir is None:
            raise RuntimeError("Root directory not initialized.")

        clean_path = pathlib.Path(user_path)
        
        if clean_path.is_absolute():
            clean_path = pathlib.Path(clean_path.anchor).joinpath(*clean_path.parts[1:])
        
        final_path = (self.root_dir / clean_path).resolve()

        if self.root_dir not in final_path.parents and final_path != self.root_dir:
            raise PermissionError(f"Security Alert: Path traversal attempt blocked -> {user_path}")
            
        return final_path

    def _extract_text(self, node: ET.Element, tag_name: str, required: bool = True) -> str:
        """
        Helper to safely extract text from XML nodes.
        Fixes: "text is not a known attribute of None" and "str | None" errors.
        """
        found = node.find(tag_name)
        
        if found is None:
            if required:
                raise ValueError(f"Missing required tag: <{tag_name}>")
            return ""
            
        # FIX 2: Handle case where tag exists but content is None (e.g. <path/>)
        if found.text is None:
            return ""
            
        return found.text

    def process_xml(self, xml_content: str):
        try:
            root = ET.fromstring(xml_content)
            if root.tag != ROOT_TAG:
                return
            
            ConsoleColors.log("INFO", "Valid XML detected. Processing changes...")
            self.log_gui("-" * 40)
            self.log_gui("New Change Set Detected")
            
            changes = root.findall('change')
            for change in changes:
                # Use helper to guarantee non-None string
                try:
                    func = self._extract_text(change, 'function')
                    
                    if func == 'createFolder':
                        self.op_create_folder(change)
                    elif func == 'writeFile':
                        self.op_write_file(change)
                    elif func == 'move':
                        self.op_move(change)
                    elif func == 'deletePath':
                        self.op_delete_path(change)
                    else:
                        ConsoleColors.log("WARN", f"Unknown function: {func}")
                except ValueError as ve:
                    ConsoleColors.log("ERROR", f"Malformed XML: {ve}")
                except Exception as e:
                    ConsoleColors.log("ERROR", f"Failed op: {e}")
                    self.log_gui(f"[ERR] {e}")

            self.log_gui("Batch Complete.")
            
        except ET.ParseError:
            pass
        except Exception as e:
            ConsoleColors.log("ERROR", f"Critical Parser Error: {e}")

    def op_create_folder(self, node: ET.Element):
        raw_path = self._extract_text(node, 'path')
        target = self.safe_path(raw_path)
        target.mkdir(parents=True, exist_ok=True)
        ConsoleColors.log("SUCCESS", f"Created Dir: {target.name}")
        self.log_gui(f"[MKDIR] {raw_path}")

    def op_write_file(self, node: ET.Element):
        raw_path = self._extract_text(node, 'path')
        # Content is optional (empty file), so required=False
        content = self._extract_text(node, 'content', required=False)
        target = self.safe_path(raw_path)
        
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
            
        ConsoleColors.log("SUCCESS", f"Wrote File: {target.name}")
        self.log_gui(f"[WRITE] {raw_path}")

    def op_move(self, node: ET.Element):
        raw_src = self._extract_text(node, 'source')
        raw_dest = self._extract_text(node, 'destination')
        
        src = self.safe_path(raw_src)
        dest = self.safe_path(raw_dest)
        
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(str(src), str(dest))
        ConsoleColors.log("SUCCESS", f"Moved: {raw_src} -> {raw_dest}")
        self.log_gui(f"[MOVE] {raw_src} -> {raw_dest}")

    def op_delete_path(self, node: ET.Element):
        raw_path = self._extract_text(node, 'path')
        target = self.safe_path(raw_path)
        
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
            
        ConsoleColors.log("SUCCESS", f"Deleted: {target.name}")
        self.log_gui(f"[DEL] {raw_path}")

    def check_clipboard(self):
        try:
            content = self.window.clipboard_get()
            
            if content.strip().startswith(f"<{ROOT_TAG}>"):
                current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                if current_hash != self.last_hash:
                    self.last_hash = current_hash
                    self.process_xml(content)
                    
        except tk.TclError:
            pass
        except Exception as e:
            print(f"Clipboard Error: {e}")
        
        self.window.after(POLL_INTERVAL_MS, self.check_clipboard)

if __name__ == "__main__":
    try:
        app = GeminiAutomator()
    except KeyboardInterrupt:
        print("\nShutting down.")