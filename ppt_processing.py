import os
import shutil
import subprocess
import sys
import time

import option

WINDOWS = sys.platform == 'win32'

from option import get_executable_path

def download_ppt(version, arg_ans, arg_pdf, CACHE_FOLDER, DOWNLOAD_FOLDER, ARIA2C_PATH, ppt_raw_data, name_prefix: str = ""):
    print(f"Downloading {name_prefix}")

    FFMPEG_PATH = get_executable_path("ffmpeg")
    ARIA2C_PATH = get_executable_path("aria2c")
    M3U8DL_PATH = get_executable_path("N_m3u8DL-RE")

    print(f"\nFinal FFMPEG Path: {FFMPEG_PATH}")
    print(f"Final ARIA2C Path: {ARIA2C_PATH}")
    print(f"Final M3U8DL Path: {M3U8DL_PATH}")

    if version == 1:
        name_prefix += "-" + ppt_raw_data['data']['title'].rstrip()
    else:
        name_prefix += "-" + ppt_raw_data['data']['presentation']['title'].rstrip()

    name_prefix = option.windows_filename_sanitizer(name_prefix)

    # If PDF is present, skip
    if os.path.exists(f"{DOWNLOAD_FOLDER}/{name_prefix}.pdf"):
        print(f"Skipping {name_prefix} - PDF already present")
        time.sleep(0.25)
        return

    os.makedirs(f"{DOWNLOAD_FOLDER}/{name_prefix}", exist_ok=True)

    images = []

    if version == 1:
        with open(f"{CACHE_FOLDER}/ppt_download.txt", "w", encoding='utf-8') as f:
            for slide in ppt_raw_data['data']['slides']:
                if not slide.get('Cover'):
                    continue

                f.write(f"{slide['Cover']}\n out={DOWNLOAD_FOLDER}/{name_prefix}/{slide['Index']}.jpg\n")
                images.append(f"{DOWNLOAD_FOLDER}/{name_prefix}/{slide['Index']}.jpg")

    else:
        with open(f"{CACHE_FOLDER}/ppt_download.txt", "w", encoding='utf-8') as f:
            for slide in ppt_raw_data['data']['slides']:
                if not slide.get('cover'):
                    continue

                f.write(f"{slide['cover']}\n out={DOWNLOAD_FOLDER}/{name_prefix}/{slide['index']}.jpg\n")
                images.append(f"{DOWNLOAD_FOLDER}/{name_prefix}/{slide['index']}.jpg")

    ppt_download_command = (f"{ARIA2C_PATH} -i {CACHE_FOLDER}/ppt_download.txt -x 16 -j 16 -c "
                            f"-l aria2c_ppt.log --log-level warn")

    if WINDOWS:
        subprocess.run(['powershell', '-Command', ppt_download_command], text=True)
    else:
        subprocess.run(ppt_download_command, shell=True)

    from PIL import Image

    if arg_ans and version != 1:
        from PIL import ImageDraw, ImageFont

        for problem in ppt_raw_data['data']['slides']:
            if problem['problem'] is None:
                continue

            if not problem.get('cover'):
                continue

            answer = "Answer: " + "; ".join(problem['problem']['content']['answer'])

            image = Image.open(f"{DOWNLOAD_FOLDER}/{name_prefix}/{problem['index']}.jpg").convert("RGB")

            draw = ImageDraw.Draw(image)

            # Load the font
            font = ImageFont.load_default(size=40)
            text_bbox = draw.textbbox(xy=(20, 20), text=answer, font=font)

            # Add semi-transparent black rectangle
            draw.rectangle([text_bbox[0] - 10, text_bbox[1] - 10, text_bbox[2] + 10, text_bbox[3] + 10], fill="#bbb")

            # Draw the text on top (white)
            draw.text((text_bbox[0], text_bbox[1]), answer, anchor="lt", font=font, fill="#333")

            image.save(f"{DOWNLOAD_FOLDER}/{name_prefix}/{problem['index']}-ans.jpg")

            # Replace the image in the list
            images[images.index(
                f"{DOWNLOAD_FOLDER}/{name_prefix}/{problem['index']}.jpg")] = f"{DOWNLOAD_FOLDER}/{name_prefix}/{problem['index']}-ans.jpg"

            print(f"Added Answer to {name_prefix} - {problem['index']}")

    if not arg_pdf:
        return

    print(f"Converting {name_prefix}")

    images = [Image.open(i) for i in images]
    images[0].save(f"{DOWNLOAD_FOLDER}/{name_prefix}.pdf", "PDF", resolution=100.0, save_all=True,
                   append_images=images[1:])

    print(f"Converted {name_prefix}")

    # can be done like this TODO
    # l2 = map(lambda x: x['B2'], ppt_raw_data['data']['slides'])
