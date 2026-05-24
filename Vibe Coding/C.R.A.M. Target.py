import os
import sys
import shutil
import re

# --- CONFIGURATION ---
# The name of the folder where all versions will be stored.
VERSIONS_FOLDER = "versions"
# The name of the file that lists which files/folders to copy.
TARGET_FILE = "target.txt"
# The name of the aggregate file for AI ingestion.
AGGREGATE_FILENAME = "codebase.txt"
# The name of the sub-folder for individual file copies.
INDIVIDUAL_FILES_DIR = "codebase"

# A set of file extensions to automatically skip. Add/remove as needed.
# The check is case-insensitive.
NON_TEXT_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.tif', '.tiff', '.webp',
    # Audio & Video
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a',
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
    # Archives
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    # Documents & Compiled Code
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.exe', '.dll', '.so', '.bin', '.pyc', '.class', '.jar',
    '.sqlite', '.db',
    # Fonts
    '.ttf', '.otf', '.woff', '.woff2',
}
# ---------------------

def get_script_directory():
    """Gets the directory where the script is located."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_next_version_number(versions_path):
    """
    Scans the versions directory to find the highest existing version number
    and returns the next number in the sequence.
    """
    if not os.path.isdir(versions_path):
        print(f"'{VERSIONS_FOLDER}' directory not found. Starting with V1.")
        return 1
        
    highest_version = 0
    try:
        for folder_name in os.listdir(versions_path):
            # Use regex to find folders starting with 'V' followed by a number.
            match = re.match(r'V(\d+)', folder_name, re.IGNORECASE)
            if match:
                version_num = int(match.group(1))
                if version_num > highest_version:
                    highest_version = version_num
    except OSError as e:
        print(f"Error reading versions directory: {e}")
        return -1 

    return highest_version + 1

def get_files_to_process(target_file_path, base_dir):
    """
    Reads the target.txt file and returns a list of absolute paths for all
    files that need to be processed.
    """
    all_files = set() 

    with open(target_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue 

            if os.path.isabs(line):
                path = line
            else:
                path = os.path.join(base_dir, line)
            
            if not os.path.exists(path):
                print(f"  [Warning] Path not found, skipping: {line}")
                continue

            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for name in files:
                        file_path = os.path.join(root, name)
                        # Avoid processing the versions folder if it's inside the base_dir
                        if VERSIONS_FOLDER in file_path:
                            continue
                        all_files.add(os.path.abspath(file_path))
            elif os.path.isfile(path):
                all_files.add(os.path.abspath(path))

    return list(all_files)

def create_version_snapshot(version_root_path, file_list, base_dir):
    """
    1. Creates a 'codebase' subfolder for individual files.
    2. Copies files into that subfolder (mangled names).
    3. Aggregates all contents into a single 'codebase.txt' file in the root.
    """
    if not file_list:
        print("No files found to process. Exiting.")
        return 0, 0

    # Create sub-directory for individual files
    individual_files_path = os.path.join(version_root_path, INDIVIDUAL_FILES_DIR)
    os.makedirs(individual_files_path, exist_ok=True)
    
    # Prepare the aggregate file path
    aggregate_file_path = os.path.join(version_root_path, AGGREGATE_FILENAME)
    
    print(f"\nProcessing snapshot in: {version_root_path}")
    
    count = 0
    skipped_count = 0

    with open(aggregate_file_path, 'w', encoding='utf-8') as agg_file:
        for source_path in file_list:
            # Determine display path
            if source_path.startswith(base_dir):
                display_path = os.path.relpath(source_path, base_dir)
            else:
                display_path = source_path

            # Skip non-text extensions
            file_ext = os.path.splitext(source_path)[1].lower()
            if file_ext in NON_TEXT_EXTENSIONS:
                print(f"  - Skipping non-text: '{display_path}'")
                skipped_count += 1
                continue

            try:
                # 1. READ CONTENT FOR AGGREGATE
                with open(source_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                agg_file.write(f"--- START OF {display_path} ---\n")
                agg_file.write(content)
                agg_file.write(f"\n--- END OF {display_path} ---\n\n")

                # 2. PHYSICAL COPY LOGIC
                if source_path.startswith(base_dir):
                    path_for_mangling = display_path 
                else:
                    path_for_mangling = source_path.replace(os.path.splitdrive(source_path)[0], '', 1)

                mangled_name = path_for_mangling.replace(os.sep, '_')
                if not mangled_name.lower().endswith('.txt'):
                    dest_name = f"{mangled_name}.txt"
                else:
                    dest_name = mangled_name

                dest_path = os.path.join(individual_files_path, dest_name)
                
                # Copying the file
                shutil.copy2(source_path, dest_path)
                
                print(f"  > Processed '{display_path}'")
                count += 1
            except Exception as e:
                print(f"  [ERROR] Could not process {source_path}. Reason: {e}")
            
    return count, skipped_count

def main():
    """Main execution function."""
    base_dir = get_script_directory()
    versions_dir = os.path.join(base_dir, VERSIONS_FOLDER)
    target_path = os.path.join(base_dir, TARGET_FILE)

    print("--- Version Creator & Codebase Aggregator ---")

    # Check if target.txt exists
    if not os.path.isfile(target_path):
        print(f"'{TARGET_FILE}' not found. Creating sample...")
        with open(target_path, 'w') as f:
            f.write("# Add file or folder paths below.\n# src/\n# README.md\n")
        print(f"'{TARGET_FILE}' created. Edit it and run again.")
        return 

    # 1. Determine the next version
    version_number = get_next_version_number(versions_dir)
    if version_number == -1:
        return 

    print(f"Next version will be: V{version_number}")
    
    # 2. Description
    description = input("Enter an optional description: ")
    version_folder_name = f"V{version_number}"
    if description:
        safe_description = re.sub(r'[^\w\s-]', '', description).strip()
        version_folder_name += f" - {safe_description}"

    new_version_root = os.path.join(versions_dir, version_folder_name)

    # 3. Get files
    print(f"\nReading targets from '{TARGET_FILE}'...")
    files_to_copy = get_files_to_process(target_path, base_dir)

    # 4. Process files and create artifacts
    copied_count, skipped_count = create_version_snapshot(new_version_root, files_to_copy, base_dir)

    # 5. Report
    summary = f"Version '{version_folder_name}' created."
    summary += f"\n- Aggregated file: {AGGREGATE_FILENAME}"
    summary += f"\n- Individual files: {INDIVIDUAL_FILES_DIR}/"
    summary += f"\n- Total processed: {copied_count}"
    
    if skipped_count > 0:
        summary += f"\n- Total skipped: {skipped_count}"

    print(f"\n--- Process Complete ---\n{summary}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        input("\nPress Enter to exit...")