import os
import re
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed


def download_segment(CACHE_FOLDER, url: str, order: int, name_prefix: str = ""):
    print(f"Downloading {name_prefix} - {order}")

    video_download_command = (f".\\aria2c -o '{CACHE_FOLDER}/{name_prefix}-{order}.mp4'"
                              f" -x 16 -s 16 '{url}' -c -l aria2c_video.log --log-level warn")

    result = subprocess.run(['powershell', '-Command', video_download_command], text=True)

    return result


def download_segment_idm(CACHE_FOLDER, url: str, order: int, name_prefix: str = ""):
    print(f"Downloading {name_prefix} - {order}")

    name_prefix_idm = name_prefix.replace('/', '\\')

    # Define the full path for the downloaded file
    downloaded_file = os.path.join(CACHE_FOLDER, f"{name_prefix_idm}-{order}.mp4")
    print("Downloading to", downloaded_file)

    if os.path.exists(downloaded_file):
        print(f"Skipping {downloaded_file} - Video already present")
        time.sleep(0.25)
        return downloaded_file

    # Construct the IDM download command
    video_download_command = (
        f"idman /n /d \"{url}\" /p \"$(pwd)\" /f \"{downloaded_file}\""
    )

    # Start the IDM download process
    subprocess.run(['powershell', '-Command', video_download_command], text=True)

    # Wait for the file to appear and its download to complete
    print(f"Waiting for {downloaded_file} to finish downloading...")
    try:
        # Wait until the file is created
        while not os.path.exists(downloaded_file):
            time.sleep(1)  # Wait until the file is created

        # Wait until the file stops growing
        prev_size = -1
        while True:
            curr_size = os.path.getsize(downloaded_file)
            if curr_size == prev_size:
                break  # File size hasn't changed, download likely complete
            prev_size = curr_size
            time.sleep(1)  # Check every second

    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
        # Optionally, clean up the partially downloaded file
        if os.path.exists(downloaded_file):
            print(f"Removing incomplete file: {downloaded_file}")
            os.remove(downloaded_file)
        raise  # Re-raise the exception to propagate it

    print(f"Download completed: {downloaded_file}")
    return downloaded_file


def download_segment_m3u8(idm_flag, CACHE_FOLDER, url: str, order: int, name_prefix: str = "", max_retries: int = 35):
    print(f"Downloading {name_prefix} - {order}")
    print(f"Downloading from {url}")

    # Initial download attempt with 32 workers

    # video_download_command = (f".\\ffmpeg -i '{url}' -c copy -n '{CACHE_FOLDER}/{name_prefix}-{order}.mp4'"
    #                           f" -hide_banner -loglevel error -stats")

    # video_download_command = (f".\\HLSDownloader -u '{url}' -o '{CACHE_FOLDER}/{name_prefix}-{order}.mp4'"
    #                           f" -w 32 -workers 32 ")

    # video_download_command = (f".\\m3u8dl-windows-amd64.exe -i '{url}' -o '{CACHE_FOLDER}/{name_prefix}-{order}.mp4'"
    #                           f" -retry 1 -t '{CACHE_FOLDER}' -thread 32")

    # video_download_command = (
    #     f".\\vsd.exe save '{url}' -o '{CACHE_FOLDER}/{name_prefix}-{order}.mp4' "
    #     f"-d {CACHE_FOLDER} --retry-count 15 -t 4")

    output_path = f"{CACHE_FOLDER}/{name_prefix}-{order}"
    save_dir = os.path.dirname(output_path)
    save_name = os.path.basename(output_path)

    if 'mp3' in url:
        if idm_flag:
            video_download_command = (
                f"idman /n /d \"{url}\" /p \"$(pwd)\" /f '{CACHE_FOLDER}/{name_prefix}-{order}.mp4'"
            )
        else:
            video_download_command = (
                f".\\ffmpeg -i '{url}' -c:v copy -c:a copy -n '{CACHE_FOLDER}/{name_prefix}-{order}.mp4' "
                f"-hide_banner -loglevel error -stats"
            )

    else:
        video_download_command = (
            f".\\N_m3u8DL-RE.exe '{url}' --tmp-dir './{CACHE_FOLDER}' "
            f"--save-dir '{save_dir}' --save-name '{save_name}' -M format=mp4 "
            f"--check-segments-count false --download-retry-count 15 --thread-count 64"
        )

    result = subprocess.run(['powershell', '-Command', video_download_command], text=True)

    return result


def download_segments_in_parallel(idm_flag, fallback_flag, CACHE_FOLDER, lesson_video_data, name_prefix):
    has_error = False

    # MOOC TYPE
    if fallback_flag == 2:
        # Create a ThreadPoolExecutor to manage parallel downloads
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Dictionary to hold future results
            future_to_order = {}

            for order, url in enumerate(lesson_video_data):
                if idm_flag:
                    future = executor.submit(download_segment_idm, CACHE_FOLDER, url, order, name_prefix)
                else:
                    future = executor.submit(download_segment, CACHE_FOLDER, url, order, name_prefix)

                # Store the future and order for tracking
                future_to_order[future] = order

                # Add a 1-second interval between submissions
                time.sleep(1)

            # Iterate over the completed futures
            for future in as_completed(future_to_order):
                order = future_to_order[future]
                try:
                    future.result()  # Get the result (will raise exception if there was one)
                    print(f"Successfully downloaded {name_prefix} - {order}")
                except Exception:
                    print(traceback.format_exc())
                    print(f"Failed to download {name_prefix} - {order}", file=sys.stderr)
                    has_error = True

    # v1 type
    elif fallback_flag == 1:
        # Create a ThreadPoolExecutor to manage parallel downloads
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Dictionary to hold future results
            future_to_order = {}

            for order, segment in enumerate(lesson_video_data['data']['live_timeline']):
                replay_url = segment['replay_url']

                # Determine which function to use based on the presence of 'm3u8' in the replay_url
                if 'm3u8' in replay_url:
                    future = executor.submit(download_segment_m3u8, idm_flag, CACHE_FOLDER, replay_url, order,
                                             name_prefix,
                                             max_retries=10)
                else:
                    if idm_flag:
                        future = executor.submit(download_segment_idm, CACHE_FOLDER, replay_url, order, name_prefix)
                    else:
                        future = executor.submit(download_segment, CACHE_FOLDER, replay_url, order, name_prefix)

                # Store the future and order for tracking
                future_to_order[future] = order

                # Add a 1-second interval between submissions
                time.sleep(1)

            # Iterate over the completed futures
            for future in as_completed(future_to_order):
                order = future_to_order[future]
                try:
                    future.result()  # Get the result (will raise exception if there was one)
                    print(f"Successfully downloaded {name_prefix} - {order}")
                except Exception:
                    print(traceback.format_exc())
                    print(f"Failed to download {name_prefix} - {order}", file=sys.stderr)
                    has_error = True

    # v3 type
    else:
        # Create a ThreadPoolExecutor to manage parallel downloads
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Dictionary to hold future results
            future_to_order = {}

            for order, segment in enumerate(lesson_video_data['data']['live']):
                url = segment['url']

                # Determine which function to use based on the presence of 'm3u8' in the URL
                if 'm3u8' in url:
                    future = executor.submit(download_segment_m3u8, idm_flag, CACHE_FOLDER, url, order, name_prefix,
                                             max_retries=10)
                else:
                    if idm_flag:
                        future = executor.submit(download_segment_idm, CACHE_FOLDER, url, order, name_prefix)
                    else:
                        future = executor.submit(download_segment, CACHE_FOLDER, url, order, name_prefix)

                # Store the future and order for tracking
                future_to_order[future] = order

                # Add a 1-second interval between submissions
                time.sleep(1)

            # Iterate over the completed futures
            for future in as_completed(future_to_order):
                order = future_to_order[future]
                try:
                    future.result()  # Get the result (will raise exception if there was one)
                    print(f"Successfully downloaded {name_prefix} - {order}")
                except Exception:
                    print(traceback.format_exc())
                    print(f"Failed to download {name_prefix} - {order}", file=sys.stderr)
                    has_error = True

    return has_error


def concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix, num_segments):
    # Create the concat file with segment paths
    with open(f"{CACHE_FOLDER}/concat.txt", "w", encoding='utf-8') as f:
        for i in range(num_segments):
            video_file_mp4 = f"../{CACHE_FOLDER}/{name_prefix}-{i}.mp4"
            video_file_ts = f"../{CACHE_FOLDER}/{name_prefix}-{i}.ts"
            if os.path.exists(os.path.join(CACHE_FOLDER, f"{name_prefix}-{i}.mp4")):  # Check if the file exists
                f.write(f"file '{video_file_mp4}'\n")
            if os.path.exists(os.path.join(CACHE_FOLDER, f"{name_prefix}-{i}.ts")):  # Check if the file exists
                f.write(f"file '{video_file_ts}'\n")

    target_file = os.path.join(DOWNLOAD_FOLDER, f"{name_prefix}.mp4")
    if os.path.exists(target_file):
        print(f"Skipping '{DOWNLOAD_FOLDER}/{name_prefix}.mp4' - Video already present")
        time.sleep(0.25)
        return target_file

    # First video concatenation command using CUDA acceleration
    video_concatenating_command = (
        f"ffmpeg -f concat -safe 0 -hwaccel cuda -hwaccel_output_format cuda "
        f"-i '{CACHE_FOLDER}/concat.txt' "
        f"-c:v av1_nvenc -cq 28 -surfaces 64 -bufsize 12800k -r 7.5 -rc-lookahead 63 "
        f"-c:a aac -ac 1 -rematrix_maxval 1.0 -b:a 64k '{DOWNLOAD_FOLDER}/{name_prefix}.mp4' -n "
        f"-hide_banner -loglevel error -stats"
    )

    # Run the first command
    result = subprocess.run(['powershell', '-Command', video_concatenating_command], text=True)

    # If the first command fails, try the fallback
    if result.returncode != 0:
        print(f"First attempt failed. Attempting fallback with software encoding.")

        # Fallback video concatenation command using cuvid acceleration
        video_concatenating_command_fallback = (
            f"ffmpeg -f concat -safe 0 "
            f"-i '{CACHE_FOLDER}/concat.txt' "
            f"-c:v av1_nvenc -cq 28 -surfaces 64 -bufsize 12800k -r 7.5 -rc-lookahead 63 "
            f"-c:a copy '{DOWNLOAD_FOLDER}/{name_prefix}.mp4' -y "
            f"-hide_banner -loglevel error -stats -err_detect ignore_err -fflags +discardcorrupt"
        )

        # Run the fallback command
        fallback_result = subprocess.run(['powershell', '-Command', video_concatenating_command_fallback], text=True)

        # Check if the fallback also fails
        if fallback_result.returncode != 0:
            print(f"Both attempts failed to concatenate video segments.")
        else:
            print(f"Successfully concatenated video segments.")
    else:
        print(f"Successfully concatenated video segments using CUDA acceleration.")

    return result
