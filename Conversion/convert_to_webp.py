# convert_to_webp.py

import subprocess
import sys
from pathlib import Path

# --- Configuration ---
# You can change the quality setting here. 85 is a great starting point for web images.
# Lower value = smaller file size, lower quality.
# Higher value = larger file size, higher quality.
WEBP_QUALITY = 85

# --- Script Logic ---

def check_imagemagick():
    """Checks if the 'magick' command is available in the system's PATH."""
    try:
        # Use a simple command to check for ImageMagick's presence
        subprocess.run(
            ['magick', '-version'],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("-------------------------------------------------------------------")
        print("ERROR: ImageMagick not found.")
        print("Please install ImageMagick and ensure the 'magick' command")
        print("is available in your system's PATH.")
        print("Installation guide: https://imagemagick.org/script/download.php")
        print("-------------------------------------------------------------------")
        return False

def convert_images_in_current_directory():
    """Finds all PNG files in the current directory and converts them to WebP."""
    current_dir = Path('.')
    # Use glob to find all files ending with .png (case-insensitive)
    png_files = list(current_dir.glob('*.[pP][nN][gG]'))

    if not png_files:
        print("No PNG files found in this directory.")
        return

    print(f"Found {len(png_files)} PNG file(s) to process.")
    
    converted_count = 0
    skipped_count = 0

    for png_path in png_files:
        webp_path = png_path.with_suffix('.webp')

        # Check if the WebP file already exists
        if webp_path.exists():
            print(f"-> Skipping '{png_path.name}', as '{webp_path.name}' already exists.")
            skipped_count += 1
            continue

        print(f"-> Converting '{png_path.name}' to '{webp_path.name}'...")

        # Construct the ImageMagick command
        # -quality: Sets the compression level (0-100)
        # -define webp:method=6: Use the slowest compression method for the best result
        # -strip: Removes all profiles and comments (reduces file size)
        command = [
            'magick',
            str(png_path),
            '-quality', str(WEBP_QUALITY),
            '-define', 'webp:method=6',
            '-strip',
            str(webp_path)
        ]

        try:
            # Execute the command
            result = subprocess.run(
                command,
                check=True,         # Raises an exception if the command fails
                capture_output=True,# Captures stdout and stderr
                text=True           # Decodes output as text
            )
            print(f"   Success! '{webp_path.name}' created.")
            converted_count += 1
        except subprocess.CalledProcessError as e:
            # This handles errors from ImageMagick itself (e.g., corrupt input file)
            print(f"   ERROR converting '{png_path.name}':")
            print(f"     Command failed with exit code {e.returncode}")
            print(f"     Stderr: {e.stderr.strip()}")

    print("\n--- Conversion Summary ---")
    print(f"Successfully converted: {converted_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print("--------------------------")


if __name__ == "__main__":
    if check_imagemagick():
        convert_images_in_current_directory()
    else:
        # Exit with an error code if the prerequisite is not met
        sys.exit(1)