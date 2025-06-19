# -*- coding: utf-8 -*-

import os
import sys
import argparse
import time
import re
import traceback
import option
import shutil

if sys.platform == 'win32':
    os.system('chcp 65001')


parser = argparse.ArgumentParser()

parser.add_argument("-c", "--session-cookie", help="Session Cookie", required=False)
parser.add_argument("-y", "--ykt-host", help="RainClassroom Host", required=False, default="pro.yuketang.cn")
idm_sel_group = parser.add_mutually_exclusive_group()
idm_sel_group.add_argument("-i", "--idm", action="store_true", help="Use IDMan.exe")
idm_sel_group.add_argument("-ni", "--no-idm", action="store_true", help="Don't use IDMan.exe, implied when the system "
                                                                        "is not Windows")
content_sel_group = parser.add_mutually_exclusive_group(required=True)
content_sel_group.add_argument("-da", "--download-all", action="store_true", help="Download all content without asking")
content_sel_group.add_argument("-dq", "--download-ask", action="store_true", help="Ask before downloading each course")
content_sel_group.add_argument("-ds", "--download-select", action="store_true", help="Select courses to download "
                                                                                     "before downloading")
parser.add_argument("-nh", "--no-hw-decoding", action="store_true", help="Don't use hardware encoding")
parser.add_argument("-nv", "--no-video", action="store_true", help="Don't Download Video")
parser.add_argument("-np", "--no-ppt", action="store_true", help="Don't Download PPT")
parser.add_argument("-npc", "--no-convert-ppt-to-pdf", action="store_true", help="Don't Convert PPT to PDF")
parser.add_argument("-npa", "--no-ppt-answer", action="store_true", help="Don't Store PPT Problem Answer")
parser.add_argument("-np2", "--no-ppt-type2", action="store_true", help="Don't Download Type 2 PPT (requires selenium)")
parser.add_argument("-cnf", "--course-name-filter", action="append", help="Filter Course Name", default=None)
parser.add_argument("-lnf", "--lesson-name-filter", action="append", help="Filter Lesson Name", default=None)

original_format_help = parser.format_help


def format_help():
    return original_format_help() + """
requirements:
    - Python >= 3.12
    - requests
    - websocket-client (qrcode login)
    - qrcode (qrcode login)
    - Pillow (Add answer to problem; Convert PPT to PDF)

    - aria2c (Download files multi-threaded & resume support)
    - ffmpeg with nvenc support (Concatenate video segments and convert to HEVC)
"""


parser.format_help = format_help

original_print_help = parser.print_help


def print_help(file=None):
    original_print_help(file)
    if sys.platform == 'win32':
        print('\nYOU SHALL RUN THIS EXECUTABLE FROM POWERSHELL WITH ARGUMENT!!')
        os.system('pause')


parser.print_help = print_help

args = parser.parse_args()

args.__setattr__('video', not args.no_video)
args.__setattr__('ppt', not args.no_ppt)
args.__setattr__('ppt_to_pdf', not args.no_convert_ppt_to_pdf)
args.__setattr__('ppt_problem_answer', not args.no_ppt_answer)

# Check for dependencies
try:
    import requests
except ImportError:
    print("requests is not installed. Please install it using 'pip install requests'", file=sys.stderr)
    exit(1)

if args.session_cookie is None:
    try:
        import websocket
    except ImportError:
        print("websocket-client is not installed. Please install it using 'pip install websocket-client'",
              file=sys.stderr)
        exit(1)

    try:
        import qrcode
    except ImportError:
        print("qrcode is not installed. Please install it using 'pip install qrcode'", file=sys.stderr)
        exit(1)

if args.ppt_to_pdf or args.ppt_problem_answer:
    try:
        import PIL
    except ImportError:
        print("PIL is not installed. Please install it using 'pip install pillow'", file=sys.stderr)
        exit(1)

if not args.no_ppt_type2:
    try:
        import selenium
    except ImportError:
        print("selenium is not installed. Please install it using 'pip install selenium' or use -np2", file=sys.stderr)
        exit(1)

if args.download_all:
    download_type_flag = 1
elif args.download_ask:
    download_type_flag = 0
elif args.download_select:
    download_type_flag = 2

if sys.platform != 'win32':
    print("Inferring --no-idm flag as the system is not Windows")
    args.no_idm = True

if args.idm:
    idm_flag = 1
elif args.no_idm:
    idm_flag = 0
else:
    idm_flag = option.ask_for_idm()

if idm_flag and shutil.which('IDMan.exe') is None:
    print("IDMan.exe is not found. Please install IDM and add it to PATH, or specify '--no-idm' flag", file=sys.stderr)
    exit(1)

if idm_flag and sys.platform != 'win32':
    print("WARNING: Are you sure that you want to use IDM on a non-Windows system?", file=sys.stderr)

if args.no_hw_decoding:
    hw_decoding_flag = 0
else:
    hw_decoding_flag = 1

args.__setattr__("aria2c_path", "aria2c")
if shutil.which("aria2c") is None and os.path.exists("aria2c.exe"):
    args.__setattr__("aria2c_path", os.path.join(os.getcwd(), "aria2c"))
    print(f"aria2c is not found in PATH, using local binary at {args.aria2c_path}")

if not idm_flag:
    if shutil.which(args.aria2c_path) is None:
        print("aria2c is not found. Please install aria2 and add it to PATH, or use IDM instead", file=sys.stderr)
        exit(1)

    print("IDM is not enabled, aria2c will be used for downloading")

import requests
import json

# --- --- --- Section Init --- --- --- #
# Login to RainClassroom
userinfo = {}
rainclassroom_sess = requests.session()

YKT_HOST = args.ykt_host
DOWNLOAD_FOLDER = "data"
CACHE_FOLDER = "cache"

rainclassroom_sess.headers[
    "User-Agent"] = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 "
                     "Safari/537.36 Edg/131.0.0.0")

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)

# --- --- --- Section Load Session --- --- --- #

if args.session_cookie is not None:
    rainclassroom_sess.cookies['sessionid'] = args.session_cookie

# --- --- --- Section Login --- --- --- #
else:
    import websocket
    import qrcode


    def on_message(ws, message):
        global userinfo
        userinfo = json.loads(message)
        if 'subscribe_status' in userinfo:
            ws.close()
            return

        qr = qrcode.QRCode()
        qr.add_data(userinfo["qrcode"])
        # Flush screen first
        print("\033c")
        qr.print_ascii(out=sys.stdout)
        print("请扫描二维码登录")


    def on_error(ws, error):
        print(error)


    def on_open(ws):
        ws.send(data=json.dumps({"op": "requestlogin", "role": "web", "version": 1.4, "type": "qrcode", "from": "web"}))


    # websocket数据交互
    ws = websocket.WebSocketApp(f"wss://{YKT_HOST}/wsapp/",
                                on_message=on_message,
                                on_error=on_error)
    ws.on_open = on_open
    ws.run_forever()

    # 登录
    req = rainclassroom_sess.get(f"https://{YKT_HOST}/v/course_meta/user_info")
    rainclassroom_sess.post(f"https://{YKT_HOST}/pc/web_login",
                            data=json.dumps({'UserID': userinfo['UserID'], 'Auth': userinfo['Auth']}))

# Store session
with open(f"{DOWNLOAD_FOLDER}/session.txt", "a", encoding='utf-8') as f:
    f.write("\n" + rainclassroom_sess.cookies['sessionid'] + "\n")


# --- --- --- Generic Error Handling --- --- --- #

class APIError(Exception):
    pass


def check_response(r: dict):
    if 'success' in r:
        e = not r['success']

    elif 'errcode' in r:
        e = r['errcode'] != 0

    elif 'code' in r:
        e = r['code'] != 0

    else:
        print(json.dumps(r))
        print("Unknown API return status")
        e = False

    if e:
        print(json.dumps(r))
        raise APIError()


# --- --- --- Section Get Course List --- --- --- #

# 获取自己的课程列表
shown_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/courses/list?identity=2").json()
check_response(shown_courses)

hidden_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/classroom_archive").json()
check_response(hidden_courses)

for course in hidden_courses['data']['classrooms']:
    course['classroom_id'] = course['id']

courses = shown_courses['data']['list'] + hidden_courses['data']['classrooms']

if args.course_name_filter is not None:
    courses = [c for c in courses if any(f in c['name'] for f in args.course_name_filter)]

# Show a list of courses and ask for selection
if args.download_select:
    done = False

    while not done:
        print("Courses:")
        for i, course in enumerate(courses):
            print(f"{i + 1}. {course['course']['name']}({course['name']}) - {course['teacher']['name']}")

        selection = input("Select courses to download (e.g. `1, 2, 3-5, 10`): ")

        try:
            indexes = []
            for part in selection.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    indexes.extend(range(start, end + 1))
                else:
                    indexes.append(int(part))

            selected_courses = [courses[i - 1] for i in indexes]
            courses = selected_courses
            download_type_flag = 1
            done = True
        except IndexError:
            print(traceback.format_exc())
            print("Invalid selection, please try again")

rainclassroom_sess.cookies['xtbz'] = 'ykt'


# --- --- --- Section Get Lesson List --- --- --- #


def get_lesson_list(course: dict, name_prefix: str = ""):
    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/v2/api/web/logs/learn/{course['classroom_id']}?actype=-1&page=0&offset=500&sort=-1").json()
    check_response(lesson_data)

    folder_name = f"{course['name']}-{course['teacher']['name']}"
    folder_name = option.windows_filename_sanitizer(folder_name)

    if idm_flag:
        folder_name = folder_name.replace('/', '\\')
        folder_name = re.sub(r'[“”]', '_', folder_name)

    print('folder name would be:', folder_name)

    # Rename old folder
    if os.path.exists(f"{DOWNLOAD_FOLDER}/{course['name']}"):
        os.rename(f"{DOWNLOAD_FOLDER}/{course['name']}", f"{DOWNLOAD_FOLDER}/{folder_name}")

    if os.path.exists(f"{CACHE_FOLDER}/{course['name']}"):
        os.rename(f"{CACHE_FOLDER}/{course['name']}", f"{CACHE_FOLDER}/{folder_name}")

    os.makedirs(f"{DOWNLOAD_FOLDER}/{folder_name}", exist_ok=True)
    os.makedirs(f"{CACHE_FOLDER}/{folder_name}", exist_ok=True)

    name_prefix += folder_name.rstrip() + "/"
    name_prefix = option.windows_filename_sanitizer(name_prefix)

    if args.lesson_name_filter is not None:
        lesson_data['data']['activities'] = [l for l in lesson_data['data']['activities'] if
                                             args.lesson_name_filter in l['title']]

    length = len(lesson_data['data']['activities'])

    def parse_single_lesson(index: int, lesson: dict):
        if lesson['type'] == 2:
            print('Script type detected!')
            download_lesson_video_type2(lesson, name_prefix + str(length - index))
        elif lesson['type'] in [14, 3]:
            print('Normal type detected!')
            download_lesson_video(lesson, name_prefix + str(length - index))
        elif lesson['type'] == 15:
            print('MOOCv2 type detected!')
            download_lesson_video_type15(lesson, name_prefix + str(length - index))
        elif lesson['type'] == 17:
            print('MOOCv1 type detected!')
            download_lesson_video_type17(lesson, name_prefix + str(length - index))

    if args.video:
        failed_lessons = []

        for index, lesson in enumerate(lesson_data['data']['activities']):
            if not lesson['type'] in [2, 3, 14, 15, 17]:
                continue

            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                parse_single_lesson(index, lesson)
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download video for {name_prefix} - {lesson['title']}", file=sys.stderr)
                failed_lessons.append((index, lesson))
        # TODO: FIX FAILURE BEHAVIOR
        print('sbykt may not prepare all cold data at once, rescanning for missing ones')
        time.sleep(2)
        for index, lesson in enumerate(lesson_data['data']['activities']):
            if not lesson['type'] in [2, 3, 14, 15, 17]:
                continue

            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                parse_single_lesson(index, lesson)
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download video for {name_prefix} - {lesson['title']}", file=sys.stderr)
                failed_lessons.append((index, lesson))

        # if len(failed_lessons) > 0:
        #     print('Retrying failed lessons')
        #
        #     for retry_count in range(3):
        #         if len(failed_lessons) == 0:
        #             break
        #
        #         print(f"Retry #{retry_count + 1}")
        #         still_failed_lessons = []
        #         for index, lesson in failed_lessons:
        #             try:
        #                 parse_single_lesson(index, lesson)
        #             except Exception:
        #                 print(traceback.format_exc())
        #                 print(f"Failed to download video for {name_prefix} - {lesson['title']}", file=sys.stderr)
        #                 still_failed_lessons.append((index, lesson))
        #
        #         failed_lessons = still_failed_lessons
        #
        #     if len(failed_lessons) > 0:
        #         with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
        #             for index, lesson in failed_lessons:
        #                 f.write(f"Video for {name_prefix} - {lesson['title']}\n")
        #                 f.write(json.dumps(lesson) + "\n\n\n")
        #
        #                 print(f"Video for {name_prefix} - {lesson['title']} failed to download", file=sys.stderr)

    if args.ppt:
        failed_lessons = []
        for index, lesson in enumerate(lesson_data['data']['activities']):
            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                if lesson['type'] == 2:
                    print('Script type detected!')
                    download_lesson_ppt_type2(lesson, name_prefix + str(length - index))
                elif lesson['type'] in [14, 3]:
                    print('Normal type detected!')
                    download_lesson_ppt(lesson, name_prefix + str(length - index))
                elif lesson['type'] in [15, 17]:
                    print('MOOC type has no PPT')
                elif lesson['type'] in [6, 9]:
                    print('Announcement type has no PPT')

            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download PPT for {name_prefix} - {lesson['title']}", file=sys.stderr)
                failed_lessons.append((index, lesson))

        # TODO: FIX FAILURE BEHAVIOR
        print('sbykt may not prepare all cold data at once, rescanning for missing ones')
        time.sleep(2)
        for index, lesson in enumerate(lesson_data['data']['activities']):
            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                if lesson['type'] == 2:
                    print('Script type detected!')
                    download_lesson_ppt_type2(lesson, name_prefix + str(length - index))
                elif lesson['type'] in [14, 3]:
                    print('Normal type detected!')
                    download_lesson_ppt(lesson, name_prefix + str(length - index))
                elif lesson['type'] in [15, 17]:
                    print('MOOC type has no PPT')
                elif lesson['type'] in [6, 9]:
                    print('Announcement type has no PPT')

            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download PPT for {name_prefix} - {lesson['title']}", file=sys.stderr)
                failed_lessons.append((index, lesson))

        # if len(failed_lessons) > 0:
        #     print('Retrying failed lessons')
        #
        #     for retry_count in range(3):
        #         if len(failed_lessons) == 0:
        #             break
        #
        #         print(f"Retry #{retry_count + 1}")
        #         still_failed_lessons = []
        #         for index, lesson in failed_lessons:
        #             try:
        #                 download_lesson_ppt(lesson, name_prefix + str(length - index))
        #             except Exception:
        #                 print(traceback.format_exc())
        #                 print(f"Failed to download PPT for {name_prefix} - {lesson['title']}", file=sys.stderr)
        #                 still_failed_lessons.append((index, lesson))
        #
        #         failed_lessons = still_failed_lessons
        #
        #     if len(failed_lessons) > 0:
        #         with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
        #             for index, lesson in failed_lessons:
        #                 f.write(f"PPT for {name_prefix} - {lesson['title']}\n")
        #                 f.write(json.dumps(lesson) + "\n\n\n")
        #
        #                 print(f"PPT for {name_prefix} - {lesson['title']} failed to download", file=sys.stderr)


# --- --- --- Section Download Lesson Video --- --- --- #

from video_processing import download_segments_in_parallel, concatenate_segments


def download_lesson_video(lesson: dict, name_prefix: str = ""):
    lesson_video_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/v3/lesson-summary/replay?lesson_id={lesson['courseware_id']}").json()
    try:
        check_response(lesson_video_data)
    except APIError:
        print('v3 protocol failed, falling back to v1')
        fallback_flag = 1
        lesson_video_data = rainclassroom_sess.get(
            f"https://{YKT_HOST}/v/lesson/get_lesson_replay_timeline/?lesson_id={lesson['courseware_id']}").json()
        check_response(lesson_video_data)

        print('v1 protocol detected!')
        if 'live_timeline' not in lesson_video_data['data'] or len(lesson_video_data['data']['live_timeline']) == 0:
            print(f"Skipping {name_prefix} - No Video", file=sys.stderr)
            return
    else:
        fallback_flag = 0

        if 'live' not in lesson_video_data['data']:
            print(f"Skipping {name_prefix} - No Video", file=sys.stderr)

    name_prefix += "-" + lesson['title'].rstrip()
    name_prefix = option.windows_filename_sanitizer(name_prefix)

    if idm_flag:
        name_prefix = re.sub(r'[“”]', '_', name_prefix)

    if os.path.exists(f"{DOWNLOAD_FOLDER}/{name_prefix}.mp4"):
        print(f"Skipping {name_prefix} - Video already present")
        time.sleep(0.25)
        return

    has_error = False

    # Download segments in parallel
    try:
        download_segments_in_parallel(idm_flag, fallback_flag, CACHE_FOLDER, lesson_video_data, name_prefix)
    except Exception:
        print(traceback.format_exc())
        print(f"Failed to download {name_prefix}", file=sys.stderr)
        has_error = True

    # Start concatenation if downloads were successful
    if not has_error:
        time.sleep(1)
        if 'live' in lesson_video_data['data'] and len(lesson_video_data['data']['live']) > 0:
            print(f"Concatenating {name_prefix}")
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix,
                                 len(lesson_video_data['data']['live']), hw_decoding_flag)
        elif 'live_timeline' in lesson_video_data['data'] and len(lesson_video_data['data']['live_timeline']) > 0:
            print(f"Concatenating {name_prefix}")
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix,
                                 len(lesson_video_data['data']['live_timeline']), hw_decoding_flag)
        else:
            print('concatenate cannot start due to previous failure')
    else:
        print('concatenate cannot start due to previous failure')

    if has_error:
        with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
            f.write(f"{name_prefix}\n")


def download_lesson_video_type15(lesson: dict, name_prefix: str = ""):
    mooc_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/c27/online_courseware/xty/kls/pub_news/{lesson['courseware_id']}/",
        headers={
            "Xtbz": "ykt",
            "Classroom-Id": str(lesson['classroom_id'])
        }
    ).json()
    check_response(mooc_data)

    for chapter in mooc_data['data']['content_info']:
        chapter_name = chapter['name']

        for orphan in chapter['leaf_list']:
            orphan_title = orphan['title']
            orphan_id = orphan['id']
            has_error = False

            name_prefix_orphan = name_prefix + chapter_name + " - " + orphan_title
            name_prefix_orphan = option.windows_filename_sanitizer(name_prefix_orphan)

            if idm_flag:
                name_prefix_orphan = re.sub(r'[“”]', '_', name_prefix_orphan)

            mooc_orphan_data = rainclassroom_sess.get(
                f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(orphan_id)}/",
                headers={
                    "Xtbz": "ykt",
                    "Classroom-Id": str(lesson['classroom_id'])
                }
            ).json()
            check_response(mooc_orphan_data)

            if 'data' not in mooc_orphan_data or 'content_info' not in mooc_orphan_data['data']:
                print('no media detected, skipping!')
                continue

            mooc_orphan_media_id = mooc_orphan_data['data']['content_info']['media']['ccid']
            mooc_orphan_media_data = rainclassroom_sess.get(
                f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_orphan_media_id}&provider=cc"
                f"&is_single=0&format=json"
            ).json()
            check_response(mooc_orphan_media_data)

            quality_keys = list(
                map(lambda x: (int(x[7:]), x), mooc_orphan_media_data['data']['playurl']['sources'].keys()))
            quality_keys.sort(key=lambda x: x[0], reverse=True)
            download_url_list = mooc_orphan_media_data['data']['playurl']['sources'][quality_keys[0][1]]
            # print(download_url_list)

            # Download segments in parallel
            try:
                download_segments_in_parallel(idm_flag, 2, CACHE_FOLDER, download_url_list, name_prefix_orphan)
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download {name_prefix}", file=sys.stderr)
                has_error = True

            # Start concatenation if downloads were successful
            if not has_error:
                time.sleep(0.25)
                if 'playurl' in mooc_orphan_media_data['data'] and len(download_url_list) > 0:
                    print(f"Concatenating {name_prefix}")
                    concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_orphan,
                                         len(download_url_list), hw_decoding_flag)
                else:
                    print('concatenate cannot start due to previous failure')
            else:
                print('concatenate cannot start due to previous failure')

            if has_error:
                with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
                    f.write(f"{name_prefix}\n")

        for section in chapter['section_list']:
            section_name = section['name']

            for lesson_d in section['leaf_list']:
                lesson_name = lesson_d['title']
                lesson_id = lesson_d['id']
                has_error = False

                name_prefix_lesson = name_prefix + chapter_name + " - " + section_name + " - " + lesson_name
                name_prefix_lesson = option.windows_filename_sanitizer(name_prefix_lesson)

                if idm_flag:
                    name_prefix_lesson = re.sub(r'[“”]', '_', name_prefix_lesson)

                mooc_lesson_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(lesson_id)}/",
                    headers={
                        "Xtbz": "ykt",
                        "Classroom-Id": str(lesson['classroom_id'])
                    }
                ).json()
                check_response(mooc_lesson_data)

                if 'data' not in mooc_lesson_data or 'content_info' not in mooc_lesson_data['data']:
                    print('no media detected, skipping!')
                    continue

                mooc_media_id = mooc_lesson_data['data']['content_info']['media']['ccid']

                mooc_media_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_media_id}&provider=cc&is_single=0"
                    f"&format=json"
                ).json()
                check_response(mooc_media_data)

                quality_keys = list(
                    map(lambda x: (int(x[7:]), x), mooc_media_data['data']['playurl']['sources'].keys()))
                quality_keys.sort(key=lambda x: x[0], reverse=True)
                download_url_list = mooc_media_data['data']['playurl']['sources'][quality_keys[0][1]]
                # print(download_url_list)

                # Download segments in parallel
                try:
                    download_segments_in_parallel(idm_flag, 2, CACHE_FOLDER, download_url_list, name_prefix_lesson)
                except Exception:
                    print(traceback.format_exc())
                    print(f"Failed to download {name_prefix}", file=sys.stderr)
                    has_error = True

                # Start concatenation if downloads were successful
                if not has_error:
                    time.sleep(1)
                    if 'playurl' in mooc_media_data['data'] and len(download_url_list) > 0:
                        print(f"Concatenating {name_prefix}")
                        concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_lesson,
                                             len(download_url_list), hw_decoding_flag)
                    else:
                        print('concatenate cannot start due to previous failure')
                else:
                    print('concatenate cannot start due to previous failure')

                if has_error:
                    with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
                        f.write(f"{name_prefix}\n")


def download_lesson_video_type17(lesson: dict, name_prefix: str = ""):
    mooc_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/c27/online_courseware/xty/kls/pub_news/{lesson['courseware_id']}/",
        headers={
            "Xtbz": "ykt",
            "Classroom-Id": str(lesson['classroom_id'])
        }
    ).json()
    check_response(mooc_data)

    if 'name' not in mooc_data['data']['content_info'] or 'content_info' not in mooc_data['data']:
        print('no media detected, skipping!')
        return

    only_lesson_name = mooc_data['data']['content_info']['name']
    only_lesson_id = mooc_data['data']['content_info']['id']

    has_error = False

    name_prefix_lesson = name_prefix + only_lesson_name
    name_prefix_lesson = option.windows_filename_sanitizer(name_prefix_lesson)

    if idm_flag:
        name_prefix_lesson = re.sub(r'[“”]', '_', name_prefix_lesson)

    mooc_lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(only_lesson_id)}/",
        headers={
            "Xtbz": "ykt",
            "Classroom-Id": str(lesson['classroom_id'])
        }
    ).json()
    check_response(mooc_lesson_data)

    if 'data' not in mooc_lesson_data or 'content_info' not in mooc_lesson_data['data']:
        print('no media detected, skipping!')
        return

    mooc_media_id = mooc_lesson_data['data']['content_info']['media']['ccid']

    mooc_media_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_media_id}&provider=cc&is_single=0&format=json"
    ).json()
    check_response(mooc_media_data)

    quality_keys = list(map(lambda x: (int(x[7:]), x), mooc_media_data['data']['playurl']['sources'].keys()))
    quality_keys.sort(key=lambda x: x[0], reverse=True)
    download_url_list = mooc_media_data['data']['playurl']['sources'][quality_keys[0][1]]
    # print(download_url_list)

    # Download segments in parallel
    try:
        download_segments_in_parallel(idm_flag, 2, CACHE_FOLDER, download_url_list, name_prefix_lesson)
    except Exception:
        print(traceback.format_exc())
        print(f"Failed to download {name_prefix}", file=sys.stderr)
        has_error = True

    # Start concatenation if downloads were successful
    if not has_error:
        time.sleep(1)
        if 'playurl' in mooc_media_data['data'] and len(download_url_list) > 0:
            print(f"Concatenating {name_prefix}")
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_lesson,
                                 len(download_url_list), hw_decoding_flag)
        else:
            print('concatenate cannot start due to previous failure')
    else:
        print('concatenate cannot start due to previous failure')

    if has_error:
        with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
            f.write(f"{name_prefix}\n")


def download_lesson_video_type2(lesson: dict, name_prefix: str = ""):
    # "id": 6036907, "courseware_id": "1055476"
    # https://pro.yuketang.cn/v2/api/web/cards/detlist/1055476?classroom_id=3058049

    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/v2/api/web/cards/detlist/{lesson['courseware_id']}?classroom_id={lesson['classroom_id']}").json()
    check_response(lesson_data)
    name_prefix += "-" + lesson_data['data']['Title'].strip()

    name_prefix = option.windows_filename_sanitizer(name_prefix)

    for slide in lesson_data['data']['Slides']:
        slide_id = slide['PageIndex']
        for shape in slide['Shapes']:
            if shape['ShapeType'] == 1 and 'file_title' in shape:
                file_title = shape['file_title']
                quality_keys = list(map(lambda x: (int(x[7:]), x), shape['playurls'].keys()))
                quality_keys.sort(key=lambda x: x[0], reverse=True)
                download_url_list = shape['playurls'][quality_keys[0][1]]

                name_prefix_shape = name_prefix + f" - {slide_id} - {file_title}"
                name_prefix_shape = option.windows_filename_sanitizer(name_prefix_shape)

                if idm_flag:
                    name_prefix_shape = re.sub(r'[“”]', '_', name_prefix_shape)

                # Download segments in parallel
                try:
                    download_segments_in_parallel(idm_flag, 2, CACHE_FOLDER, download_url_list, name_prefix_shape)
                    has_error = False
                except Exception:
                    print(traceback.format_exc())
                    print(f"Failed to download {name_prefix}", file=sys.stderr)
                    has_error = True

                # Start concatenation if downloads were successful
                if not has_error:
                    time.sleep(1)
                    if 'playurl' in shape and len(download_url_list) > 0:
                        print(f"Concatenating {name_prefix}")
                        concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_shape,
                                             len(download_url_list), hw_decoding_flag)
                    else:
                        print('concatenate cannot start due to previous failure')
                else:
                    print('concatenate cannot start due to previous failure')

                if has_error:
                    with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
                        f.write(f"{name_prefix}\n")


from ppt_processing import download_ppt


def download_lesson_ppt(lesson: dict, name_prefix: str = ""):
    name_prefix += "-" + lesson['title'].rstrip()
    name_prefix = option.windows_filename_sanitizer(name_prefix)

    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/v3/lesson-summary/student?lesson_id={lesson['courseware_id']}").json()
    try:
        check_response(lesson_data)
    except APIError:
        print('v3 protocol failed, falling back to v1')

        ppt_info = rainclassroom_sess.get(
            f"https://{YKT_HOST}/v2/api/web/lessonafter/{lesson['courseware_id']}/presentation?classroom_id={lesson['classroom_id']}").json()
        check_response(ppt_info)

        print('v1 protocol detected!')

        if 'id' not in ppt_info['data'][0]:
            print(f"Skipping {name_prefix} - No PPT", file=sys.stderr)
            return

        for index, ppt in enumerate(ppt_info['data']):
            # PPT
            try:
                ppt_raw_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/v2/api/web/lessonafter/presentation/{ppt['id']}?classroom_id={lesson['classroom_id']}").json()
                check_response(ppt_raw_data)
                download_ppt(1, args.ppt_problem_answer, args.ppt_to_pdf, CACHE_FOLDER, DOWNLOAD_FOLDER,
                             args.aria2c_path,
                             ppt_raw_data, name_prefix + f"-{index}")

            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download PPT {name_prefix} - {ppt['title']}", file=sys.stderr)

    for index, ppt in enumerate(lesson_data['data']['presentations']):
        # PPT
        try:
            ppt_raw_data = rainclassroom_sess.get(
                f"https://{YKT_HOST}/api/v3/lesson-summary/student/presentation?presentation_id={ppt['id']}&lesson_id={lesson['courseware_id']}").json()
            check_response(ppt_raw_data)
            download_ppt(3, args.ppt_problem_answer, args.ppt_to_pdf, CACHE_FOLDER, DOWNLOAD_FOLDER, args.aria2c_path,
                         ppt_raw_data, name_prefix + f"-{index}")

        except Exception:
            print(traceback.format_exc())
            print(f"Failed to download PPT {name_prefix} - {ppt['title']}", file=sys.stderr)


def download_lesson_ppt_type2(lesson: dict, name_prefix: str = ""):
    import selenium.webdriver
    from selenium.webdriver.chrome.options import Options

    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/v2/api/web/cards/detlist/{lesson['courseware_id']}?classroom_id={lesson['classroom_id']}").json()
    check_response(lesson_data)

    name_prefix = option.windows_filename_sanitizer(name_prefix)[:name_prefix.rfind('/')]

    ppt_name = lesson_data['data']['Title'] + '.pdf'

    if os.path.exists(os.path.join(DOWNLOAD_FOLDER, name_prefix, ppt_name)):
        print(f"Skipping {name_prefix}/{ppt_name} - PPT already present")
        return

    ppt_data = json.dumps(lesson_data['data']).replace("\\", "\\\\").replace("`", "\\`")

    # Create a Selenium WebDriver and set localstorage.rain_print of YKT_HOST to ppt_data
    # driver = selenium.webdriver.Chrome()
    # driver.get(f"https://{YKT_HOST}/")
    # driver.execute_script(f"localStorage.rain_print = `{ppt_data}`")

    # # Navigate to https://{YKT_HOST}/web/print and print webpage to PDF
    # driver.get(f"https://{YKT_HOST}/web/print")

    # # Print to PDF without user's interaction
    # driver.execute_script("window.print();")

    chrome_options = Options()
    chrome_options.add_argument('--kiosk-printing')
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    prefs = {
        'printing.print_preview_sticky_settings.appState': json.dumps({
            'recentDestinations': [{
                'id': 'Save as PDF',
                'origin': 'local',
                'account': '',
            }],
            'selectedDestinationId': 'Save as PDF',
            'version': 2
        }),
        'savefile.default_directory': os.path.join(os.path.abspath(DOWNLOAD_FOLDER), name_prefix)
    }
    chrome_options.add_experimental_option('prefs', prefs)

    driver = selenium.webdriver.Chrome(options=chrome_options)
    driver.get(f"https://{YKT_HOST}/")
    driver.execute_script(f"localStorage.rain_print = `{ppt_data}`")
    driver.get(f"https://{YKT_HOST}/web/print")
    time.sleep(3)
    driver.execute_script("window.print();")
    time.sleep(3)
    driver.quit()


# --- --- --- Section Main --- --- --- #

print('successfully parsed account info!')

for course in courses:
    skip_flag = 0
    try:
        print(course)
        if not download_type_flag:
            skip_flag = option.ask_for_input()
            if skip_flag:
                continue
            else:
                get_lesson_list(course)
        else:
            get_lesson_list(course)
    except Exception:
        print(traceback.format_exc())
        print(f"Failed to parse {course['name']}", file=sys.stderr)
