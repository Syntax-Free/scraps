#!/usr/bin/env python3
"""
Metadata Stripper Utility - Optimized High-Performance Version
"""

import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List

# Configuration
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class FastExifStripper:
    def __init__(self, recursive: bool = False):
        self.base_dir = Path(__file__).resolve().parent
        self.exiftool_path = self._find_exiftool()
        self.recursive = recursive
        
        # Extensions to explicitly ignore (Safety)
        self.excluded_extensions = ['py', 'sh', 'exe', 'bat', 'msi', 'js', 'json']

    def _find_exiftool(self) -> str:
        path = shutil.which("exiftool")
        if not path:
            logger.error("CRITICAL: ExifTool not found in system PATH.")
            sys.exit(1)
        return path

    def strip_metadata(self):
        """
        Executes metadata removal using ExifTool's internal directory processing.
        This is the fastest method as it minimizes process overhead.
        """
        logger.info(f"Initiating {'recursive ' if self.recursive else ''}strip in: {self.base_dir}")

        # Constructing the command
        # .                          -> Process current directory
        # -all=                      -> Strip all tags
        # -overwrite_original        -> No backup files
        # -ignoreMinorErrors         -> Skip non-fatal errors
        # -r                         -> Recursive (if enabled)
        # --ext                      -> Exclude specific extensions
        cmd = [
            self.exiftool_path,
            "-all=",
            "-overwrite_original",
            "-ignoreMinorErrors",
            "-charset", "filename=utf8", # Ensure robust filename handling
        ]

        if self.recursive:
            cmd.append("-r")

        # Dynamically exclude the script's extension and other dangerous ones
        for ext in self.excluded_extensions:
            cmd.extend(["--ext", ext])

        # Target the directory directly
        cmd.append(str(self.base_dir))

        try:
            # Using Popen to stream output in real-time for observability
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Stream stdout
            for line in process.stdout:
                line = line.strip()
                if line: logger.info(f"ExifTool: {line}")

            # Capture errors
            _, stderr = process.communicate()
            if process.returncode != 0:
                logger.error(f"ExifTool finished with errors:\n{stderr}")
            else:
                logger.info("Metadata stripping completed successfully.")

        except Exception as e:
            logger.error(f"Execution failed: {e}")

def main():
    # Set recursive=True if you want to dive into subfolders
    stripper = FastExifStripper(recursive=False)
    
    # Performance Note: Targeting the directory directly allows ExifTool 
    # to use its internal file iterator which is faster than Python's.
    stripper.strip_metadata()

if __name__ == "__main__":
    # Optimize for high-speed IO
    main()