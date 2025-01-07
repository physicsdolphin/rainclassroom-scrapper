import re
import sys


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

def windows_filesame_sanitizer(input_str):
    # Remove illegal characters for Windows filenames
    input_str = re.sub(r'[<>:"\\|?*\x00-\x1F]', '_', input_str)
    input_str = re.sub(r'[\x80-\xFF]', '', input_str)
    # Step 2: Preserve the first `/` and replace the rest with underscores
    parts = input_str.split("/", 1)  # Split into two parts at the first slash
    if len(parts) > 1:
        input_str = parts[0] + "/" + parts[1].replace("/", "_")  # Preserve first slash, replace others
    else:
        input_str = parts[0]  # No slashes found
    return input_str