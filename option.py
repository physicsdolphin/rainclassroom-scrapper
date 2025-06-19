import re
import sys


import os
import shutil


def get_executable_path(name: str) -> str:
    """
    Finds an executable, correctly distinguishing between a find in the system PATH
    and a find in the current working directory.

    Args:
        name: The name of the executable (e.g., "ffmpeg").

    Returns:
        - The simple `name` if found in a system PATH directory.
        - The full, absolute path if found in the current working directory.
        - The full, absolute path if found alongside the script (as a fallback).

    Raises:
        FileNotFoundError: If the executable cannot be found anywhere.
    """
    # 1. Use the standard library's robust tool to find the executable.
    found_path = shutil.which(name)

    # 2. If it's not found by `shutil.which`, it's not in the PATH or the CWD.
    if found_path is None:
        # As a final fallback, check for the executable alongside the script itself.
        # This is the most reliable method for bundled applications.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(script_dir, f"{name}.exe" if os.name == 'nt' else name)

        if os.path.isfile(local_path):
            print(f"INFO: '{name}' not in PATH/CWD, using version alongside script: {local_path}")
            return local_path
        else:
            raise FileNotFoundError(
                f"'{name}' could not be found in the system PATH, current directory, "
                "or alongside the script."
            )

    # 3. If it was found, we need to determine WHERE.
    # Get the absolute, normalized path of the found executable's directory.
    found_dir = os.path.dirname(os.path.abspath(found_path))

    # Get the absolute, normalized path of the current working directory.
    cwd = os.getcwd()

    # 4. Compare the directories.
    if found_dir == cwd:
        # It was found in the current working directory. This is our "local" case.
        print(f"INFO: '{name}' found in the current working directory.")
        return os.path.abspath(found_path)  # Return the full path to be explicit.
    else:
        # It was found in a different directory, which must be from the PATH.
        print(f"INFO: '{name}' found in system PATH.")
        return name  # Return the simple name and let the OS resolve it.


def ask_for_input():
    while True:
        user_input = input("Do you want to continue/abort/skip_current? (y/n/s): ").lower()
        if user_input == 'y':
            print("Proceeding...")
            return 0  # Don't skip
        elif user_input == 'n':
            print("Aborting the program.")
            sys.exit()  # Exit the program if 'n' is chosen
        elif user_input == 's':
            print("Skipping current...")
            return 1  # Set skip_flag to 1
        else:
            print("Invalid input, please enter 'y', 'n', or 's'.")


def ask_for_allin():
    while True:
        print('asking for whether to download all at once...')
        confirmation = input(
            "All in Means download everything at once.\n"
            "This may take a long time and require over 100G of disk space.\n"
            " Are you sure? (y/n): ").lower()
        if confirmation == 'y':
            print("All in! Ensure more than 100G disk space available in current directory!!!")
            print("May take a looooooong time to finish!!!")
            return 1  # Set allin_flag to 1
        elif confirmation == 'n':
            print("Cancelled 'All in' operation.")
            return 0
        else:
            print("Invalid input, please enter 'y' or 'n'.")


def ask_for_idm():
    while True:
        print('asking for whether to download with IDM...')
        confirmation = input(
            "IDM is a fast parallel downloader.\n"
            "You need to install IDM and add idman.exe to SYSTEM PATH!!!\n"
            "Without installing IDM the script won't run!!!!!!!!\n"
            " Are you sure? (y/n): ").lower()
        if confirmation == 'y':
            print("Choosing IDM as download method")
            print("Enjoy fast downloading")
            return 1  # Set idm_flag to 1
        elif confirmation == 'n':
            print("Choosing default download method")
            return 0
        else:
            print("Invalid input, please enter 'y' or 'n'.")


def windows_filename_sanitizer(input_str):
    # Remove illegal characters for Windows filenames
    input_str = re.sub(r'[<>:"\\|?*\x00-\x1F]', '_', input_str)
    input_str = re.sub(r'[\x80-\xFF]', '', input_str)
    # Step 2: Preserve the first `/` and replace the rest with underscores
    parts = input_str.split("/", 1)  # Split into two parts at the first slash
    if len(parts) > 1:
        input_str = parts[0] + "/" + parts[1].replace("/", "_")  # Preserve first slash, replace others
    else:
        input_str = parts[0]  # No slashes found
    return input_str[:180]
