import sys, re, os, time, argparse, gc
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

try:
    import pathspec
except ImportError:
    print("Error: 'pathspec' missing. Run: pip install pathspec"); sys.exit(1)

ROOT = Path(__file__).resolve().parent
VERSIONS_DIR_NAME = "versions"

IGNORES = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", 
    ".idea", ".vscode", ".DS_Store", ".mypy_cache", ".pytest_cache",
    "dist", "build", "target", VERSIONS_DIR_NAME
}

TEXT_EXTS = {
    '.py', '.js', '.ts', '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.php', '.html', '.css', 
    '.scss', '.json', '.yaml', '.yml', '.md', '.txt', '.xml', '.sql', '.sh', '.bat', '.ps1',
    '.java', '.rb', '.pl', '.lua', '.toml', '.ini', '.cfg', '.env', '.gitignore', '.gcignore'
}

NON_TEXT = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.mp3', '.mp4', '.zip', '.7z', 
    '.pdf', '.exe', '.pyc', '.dll', '.bin', '.doc', '.docx', '.xls', '.xlsx',
    '.sqlite', '.db', '.dat', '.rlib', '.o', '.obj', '.ttf', '.woff'
}

class BackupSystem:
    def __init__(self, desc=None, batch=False):
        self.lock = Lock()
        self.v_num = self._get_v()
        
        if not desc and not batch:
            try: desc = input(f"Next Version V{self.v_num} - Description (optional): ").strip()
            except KeyboardInterrupt: sys.exit(0)
        
        safe_desc = f" - {re.sub(r'[<>:/\\|?*]', '', desc)}" if desc else ""
        self.out_path = ROOT / VERSIONS_DIR_NAME / f"V{self.v_num}{safe_desc}"
        self.code_dir = self.out_path / "codebase"
        self.agg_file = self.out_path / "codebase.txt"
        self.spec = self._load_spec()

    def _get_v(self):
        v_dir = ROOT / VERSIONS_DIR_NAME
        if not v_dir.exists(): return 1
        nums = []
        try:
            for d in v_dir.iterdir():
                if d.is_dir():
                    match = re.match(r'^[Vv](\d+)', d.name)
                    if match: nums.append(int(match.group(1)))
        except OSError: pass
        return max(nums, default=0) + 1

    def _load_spec(self):
        lines = [Path(__file__).name, ".gitignore", ".gcignore", VERSIONS_DIR_NAME, "*.pyc"] 
        lines.extend([f"{x}/" for x in IGNORES])
        for f_name in [".gitignore", ".gcignore"]:
            f_path = ROOT / f_name
            if f_path.exists():
                lines.extend(f_path.read_text(errors='ignore').splitlines())
        return pathspec.PathSpec.from_lines('gitwildmatch', lines)

    def scan(self):
        candidates = []
        spec_match = self.spec.match_file
        def _walk(curr, rel_str):
            try:
                with os.scandir(curr) as it:
                    for entry in it:
                        e_rel = f"{rel_str}/{entry.name}" if rel_str else entry.name
                        if entry.is_dir():
                            if entry.name in IGNORES or spec_match(e_rel) or spec_match(e_rel + "/"): continue
                            _walk(entry.path, e_rel)
                        elif entry.is_file():
                            ext = Path(entry.name).suffix.lower()
                            if ext in NON_TEXT or spec_match(e_rel): continue
                            candidates.append((entry.path, e_rel, ext))
            except (OSError, PermissionError): pass
        _walk(str(ROOT), "")
        return candidates

    def process_file(self, task, agg_handle):
        src, rel, ext = task
        flat = rel.replace("/", "__").replace("\\", "__")
        if not flat.lower().endswith(".txt"): flat += ".txt"
        dest = self.code_dir / flat
        
        try:
            # Check for null bytes if unknown extension
            if ext not in TEXT_EXTS:
                with open(src, 'rb') as f:
                    if b'\0' in f.read(1024): return False 
            
            file_data = Path(src).read_bytes()
            
            # Write individual file
            with open(dest, 'wb') as f:
                f.write(file_data)
            
            header = f"--- START OF {rel} ---\n".encode()
            footer = f"\n--- END OF {rel} ---\n\n".encode()
            
            # Write to aggregate using shared handle and lock
            with self.lock:
                agg_handle.write(header + file_data + footer)
                agg_handle.flush() # Force write to disk
            return True
        except Exception:
            return False

    def run(self):
        start = time.perf_counter()
        print(f"Scanning: {ROOT}")
        files = self.scan()
        if not files: return print("Nothing to back up.")
        
        self.code_dir.mkdir(parents=True, exist_ok=True)
        
        # Open aggregate file ONCE and pass the handle
        agg_handle = open(self.agg_file, 'ab')
        executor = ThreadPoolExecutor(max_workers=os.cpu_count()*4)
        
        try:
            results = list(executor.map(lambda f: self.process_file(f, agg_handle), files))
        finally:
            # CRITICAL: Close handles and shutdown threads NO MATTER WHAT
            executor.shutdown(wait=True)
            agg_handle.close()
            # Help Python release objects immediately
            del agg_handle
            gc.collect() 

        duration = time.perf_counter() - start
        print(f"Done! {sum(results)} files processed in {duration:.3f}s")
        print(f"Saved to: {self.out_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--desc", help="Version description")
    p.add_argument("-b", "--batch", action="store_true", help="Skip description prompt")
    args = p.parse_args()
    
    BackupSystem(args.desc, args.batch).run()
    
    # Final cleanup: ensure the process is ready to terminate
    sys.exit(0)