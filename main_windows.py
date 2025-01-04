import os
import sys
import argparse
import time
import re
import traceback
import option

parser = argparse.ArgumentParser(add_help=False)

parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit")
parser.add_argument("-c", "--session-cookie", help="Session Cookie", required=False)
parser.add_argument("-y", "--ykt-host", help="RainClassroom Host", required=False, default="pro.yuketang.cn")
parser.add_argument("-i", "--idm", action="store_true", help="Use IDMan.exe")
parser.add_argument("-ni", "--no-idm", action="store_true", help="Don't use IDMan.exe")
parser.add_argument("-a", "--all", action="store_true", help="All in")
parser.add_argument("-na", "--no-all", action="store_true", help="No All in")
parser.add_argument("--video", action="store_true", help="Download Video")
parser.add_argument("--ppt", action="store_true", help="Download PPT")
parser.add_argument("--ppt-to-pdf", action="store_true", help="Convert PPT to PDF", default=True)
parser.add_argument("--ppt-problem-answer", action="store_true", help="Store PPT Problem Answer", default=True)
parser.add_argument("--course-name-filter", action="store", help="Filter Course Name", default=None)
parser.add_argument("--lesson-name-filter", action="store", help="Filter Lesson Name", default=None)

# Check for no arguments and display help if none are given
if len(sys.argv) == 1:
    parser.print_help()
    print('\nYOU SHALL RUN THIS EXECUTABLE FROM POWERSHELL WITH ARGUMENT!!')
    print('YOU SHALL RUN THIS EXECUTABLE FROM POWERSHELL WITH ARGUMENT!!')
    print('YOU SHALL RUN THIS EXECUTABLE FROM POWERSHELL WITH ARGUMENT!!')
    sys.exit()

args = parser.parse_args()

# Check if no arguments are provided or only --help is provided
if args.help or len(vars(args)) == 0:
    print("""RainClassroom Video Downloader

requirements:
    - Python >= 3.12
    - requests
    - websocket-client (qrcode login)
    - qrcode (qrcode login)
    - Pillow (Add answer to problem; Convert PPT to PDF)

    - aria2c (Download files multi-threaded & resume support)
    - ffmpeg with nvenc support (Concatenate video segments and convert to HEVC)
""")
    print(parser.format_help())
    exit()

import requests
import json

# --- --- --- Section Init --- --- --- #
# Login to RainClassroom
userinfo = {}
rainclassroom_sess = requests.session()

YKT_HOST = args.ykt_host
DOWNLOAD_FOLDER = "data"
CACHE_FOLDER = "cache"

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
        f.write(rainclassroom_sess.cookies['sessionid'] + "\n")

# --- --- --- Section Get Course List --- --- --- #

# 获取自己的课程列表
shown_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/courses/list?identity=2").json()

hidden_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/classroom_archive").json()

for course in hidden_courses['data']['classrooms']:
    course['classroom_id'] = course['id']

courses = shown_courses['data']['list'] + hidden_courses['data']['classrooms']

if args.course_name_filter is not None:
    courses = [c for c in courses if args.course_name_filter in c['name']]

rainclassroom_sess.cookies['xtbz'] = 'ykt'


# --- --- --- Section Get Lesson List --- --- --- #


def get_lesson_list(course: dict, name_prefix: str = ""):
    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/v2/api/web/logs/learn/{course['classroom_id']}?actype=-1&page=0&offset=500&sort=-1").json()

    folder_name = f"{course['name']}-{course['teacher']['name']}"
    folder_name = option.windows_filesame_sanitizer(folder_name)

    if idm_flag:
        folder_name = folder_name.replace('/', '\\')
        folder_name = re.sub(r'[“”]', '_', folder_name)

    print('folder name would be:',folder_name)

    # Rename old folder
    if os.path.exists(f"{DOWNLOAD_FOLDER}/{course['name']}"):
        os.rename(f"{DOWNLOAD_FOLDER}/{course['name']}", f"{DOWNLOAD_FOLDER}/{folder_name}")

    if os.path.exists(f"{CACHE_FOLDER}/{course['name']}"):
        os.rename(f"{CACHE_FOLDER}/{course['name']}", f"{CACHE_FOLDER}/{folder_name}")

    os.makedirs(f"{DOWNLOAD_FOLDER}/{folder_name}", exist_ok=True)
    os.makedirs(f"{CACHE_FOLDER}/{folder_name}", exist_ok=True)


    name_prefix += folder_name.rstrip() + "/"
    name_prefix = option.windows_filesame_sanitizer(name_prefix)

    if args.lesson_name_filter is not None:
        lesson_data['data']['activities'] = [l for l in lesson_data['data']['activities'] if
                                             args.lesson_name_filter in l['title']]

    length = len(lesson_data['data']['activities'])

    if args.video:
        for index, lesson in enumerate(lesson_data['data']['activities']):
            if not lesson['type'] in [14, 15, 17]:
                continue

            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                if lesson['type'] == 14:
                    print('Normal type detected!')
                    download_lesson_video(lesson, name_prefix + str(length - index))
                elif lesson['type'] == 15:
                    print('MOOCv2 type detected!')
                    download_lesson_video_type15(lesson, name_prefix + str(length - index))
                elif lesson['type'] == 17:
                    print('MOOCv1 type detected!')
                    download_lesson_video_type17(lesson, name_prefix + str(length - index))
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download video for {name_prefix} - {lesson['title']}", file=sys.stderr)

        print('sbykt may not prepare cold data in one run, rescanning for missing ones')

        for index, lesson in enumerate(lesson_data['data']['activities']):
            if not lesson['type'] in [14, 15, 17]:
                continue

            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                if lesson['type'] == 14:
                    print('Normal type detected!')
                    download_lesson_video(lesson, name_prefix + str(length - index))
                elif lesson['type'] == 15:
                    print('MOOCv2 type detected!')
                    download_lesson_video_type15(lesson, name_prefix + str(length - index))
                elif lesson['type'] == 17:
                    print('MOOCv1 type detected!')
                    download_lesson_video_type17(lesson, name_prefix + str(length - index))
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download video for {name_prefix} - {lesson['title']}", file=sys.stderr)

    if args.ppt:
        for index, lesson in enumerate(lesson_data['data']['activities']):
            if lesson['type'] in (15, 17):
                print("mooc type has no ppts!")
                continue
            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                download_lesson_ppt(lesson, name_prefix + str(length - index))
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download PPT for {name_prefix} - {lesson['title']}", file=sys.stderr)

        print('sbykt may not prepare cold data in one run, rescanning for missing ones')

        for index, lesson in enumerate(lesson_data['data']['activities']):
            if lesson['type'] in (15, 17):
                print("mooc type has no ppts!")
                continue
            lesson['classroom_id'] = course['classroom_id']

            # Lesson
            try:
                download_lesson_ppt(lesson, name_prefix + str(length - index))
            except Exception:
                print(traceback.format_exc())
                print(f"Failed to download PPT for {name_prefix} - {lesson['title']}", file=sys.stderr)


# --- --- --- Section Download Lesson Video --- --- --- #

from video_processing import download_segments_in_parallel, concatenate_segments


def download_lesson_video(lesson: dict, name_prefix: str = ""):
    lesson_video_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/v3/lesson-summary/replay?lesson_id={lesson['courseware_id']}").json()

    name_prefix += "-" + lesson['title'].rstrip()
    name_prefix = option.windows_filesame_sanitizer(name_prefix)

    if idm_flag:
        name_prefix = re.sub(r'[“”]', '_', name_prefix)

    if 'live' not in lesson_video_data['data']:
        print(f"v3 protocol detection failed, falling back to v1")

        fallback_flag = 1

        lesson_video_data = rainclassroom_sess.get(
            f"https://{YKT_HOST}/v/lesson/get_lesson_replay_timeline/?lesson_id={lesson['courseware_id']}").json()

        if 'live_timeline' not in lesson_video_data['data'] or len(lesson_video_data['data']['live_timeline']) == 0:
            print(f"Skipping {name_prefix} - No Video", file=sys.stderr)
            return
    else:
        fallback_flag = 0

        if len(lesson_video_data['data']['live']) == 0:
            print(f"Skipping {name_prefix} - No Video", file=sys.stderr)
            return

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
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix, len(lesson_video_data['data']['live']))
        elif 'live_timeline' in lesson_video_data['data'] and len(lesson_video_data['data']['live_timeline']) > 0:
            print(f"Concatenating {name_prefix}")
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix,
                                 len(lesson_video_data['data']['live_timeline']))
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

    for chapter in mooc_data['data']['content_info']:
        chapter_name = chapter['name']

        for orphan in chapter['leaf_list']:
            orphan_title = orphan['title']
            orphan_id = orphan['id']
            has_error = False

            name_prefix_orphan = name_prefix + chapter_name + " - " + orphan_title
            name_prefix_orphan = option.windows_filesame_sanitizer(name_prefix_orphan)

            if idm_flag:
                name_prefix_orphan = re.sub(r'[“”]', '_', name_prefix_orphan)

            mooc_orphan_data = rainclassroom_sess.get(
                f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(orphan_id)}/",
                headers={
                    "Xtbz": "ykt",
                    "Classroom-Id": str(lesson['classroom_id'])
                }
            ).json()

            if 'data' not in mooc_orphan_data or 'content_info' not in mooc_orphan_data['data']:
                print('no media detected, skipping!')
                continue

            mooc_orphan_media_id = mooc_orphan_data['data']['content_info']['media']['ccid']
            mooc_orphan_media_data = rainclassroom_sess.get(
                f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_orphan_media_id}&provider=cc&is_single=0&format=json"
            ).json()

            quality_keys = list(map(lambda x: (int(x[7:]), x), mooc_orphan_media_data['data']['playurl']['sources'].keys()))
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
                    concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_orphan, len(download_url_list))
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
                name_prefix_lesson = option.windows_filesame_sanitizer(name_prefix_lesson)

                if idm_flag:
                    name_prefix_lesson = re.sub(r'[“”]', '_', name_prefix_lesson)

                mooc_lesson_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(lesson_id)}/",
                    headers={
                        "Xtbz": "ykt",
                        "Classroom-Id": str(lesson['classroom_id'])
                    }
                ).json()

                if 'data' not in mooc_lesson_data or 'content_info' not in mooc_lesson_data['data']:
                    print('no media detected, skipping!')
                    continue

                mooc_media_id = mooc_lesson_data['data']['content_info']['media']['ccid']

                mooc_media_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_media_id}&provider=cc&is_single=0&format=json"
                ).json()

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
                        concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_lesson, len(download_url_list))
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

    if 'name' not in mooc_data['data']['content_info'] or 'content_info' not in mooc_data['data']:
        print('no media detected, skipping!')
        return

    only_lesson_name = mooc_data['data']['content_info']['name']
    only_lesson_id = mooc_data['data']['content_info']['id']

    has_error = False

    name_prefix_lesson = name_prefix + only_lesson_name
    name_prefix_lesson = option.windows_filesame_sanitizer(name_prefix_lesson)

    if idm_flag:
        name_prefix_lesson = re.sub(r'[“”]', '_', name_prefix_lesson)

    mooc_lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/mooc-api/v1/lms/learn/leaf_info/{str(lesson['classroom_id'])}/{str(only_lesson_id)}/",
        headers={
            "Xtbz": "ykt",
            "Classroom-Id": str(lesson['classroom_id'])
        }
    ).json()

    if 'data' not in mooc_lesson_data or 'content_info' not in mooc_lesson_data['data']:
        print('no media detected, skipping!')
        return

    mooc_media_id = mooc_lesson_data['data']['content_info']['media']['ccid']

    mooc_media_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/open/audiovideo/playurl?video_id={mooc_media_id}&provider=cc&is_single=0&format=json"
    ).json()

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
            concatenate_segments(CACHE_FOLDER, DOWNLOAD_FOLDER, name_prefix_lesson, len(download_url_list))
        else:
            print('concatenate cannot start due to previous failure')
    else:
        print('concatenate cannot start due to previous failure')

    if has_error:
        with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
            f.write(f"{name_prefix}\n")


from ppt_processing import download_ppt


def download_lesson_ppt(lesson: dict, name_prefix: str = ""):
    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/v3/lesson-summary/student?lesson_id={lesson['courseware_id']}").json()
    name_prefix += "-" + lesson['title'].rstrip()

    name_prefix = option.windows_filesame_sanitizer(name_prefix)

    if 'presentations' not in lesson_data['data']:
        print(f"v3 protocol detection failed, falling back to v1")

        ppt_info = rainclassroom_sess.get(
            f"https://{YKT_HOST}/v2/api/web/lessonafter/{lesson['courseware_id']}/presentation?classroom_id={lesson['classroom_id']}").json()
        if 'id' not in ppt_info['data'][0]:
            print(f"Skipping {name_prefix} - No PPT", file=sys.stderr)
            return

        for index, ppt in enumerate(ppt_info['data']):
            # PPT
            try:
                ppt_raw_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/v2/api/web/lessonafter/presentation/{ppt['id']}?classroom_id={lesson['classroom_id']}").json()
                download_ppt(1, args.ppt_problem_answer, args.ppt_to_pdf, CACHE_FOLDER, DOWNLOAD_FOLDER,
                             ppt_raw_data, name_prefix + f"-{index}")

            except Exception as e:
                print(traceback.format_exc())
                print(f"Failed to download PPT {name_prefix} - {ppt['title']}", file=sys.stderr)

    else:
        for index, ppt in enumerate(lesson_data['data']['presentations']):
            # PPT
            try:
                ppt_raw_data = rainclassroom_sess.get(
                    f"https://{YKT_HOST}/api/v3/lesson-summary/student/presentation?presentation_id={ppt['id']}&lesson_id={lesson["courseware_id"]}").json()
                download_ppt(3, args.ppt_problem_answer, args.ppt_to_pdf, CACHE_FOLDER, DOWNLOAD_FOLDER,
                             ppt_raw_data, name_prefix + f"-{index}")

            except Exception as e:
                print(traceback.format_exc())
                print(f"Failed to download PPT {name_prefix} - {ppt['title']}", file=sys.stderr)


# --- --- --- Section Main --- --- --- #


import option as opt

print('successfully parsed account info!')

if args.all and args.no_all:
    print("'-a' and '-na' cannot be used together")
if args.idm and args.no_idm:
    print("'-idm' and '-no_idm' cannot be used together")

if args.all:
    allin_flag = 1
elif args.no_all:
    allin_flag = 0
else:
    allin_flag = opt.ask_for_allin()

if args.idm:
    idm_flag = 1
elif args.no_idm:
    idm_flag = 0
else:
    idm_flag = opt.ask_for_idm()

for course in courses:
    skip_flag = 0
    try:
        print(course)
        if not allin_flag:
            skip_flag = opt.ask_for_input()
            if skip_flag:
                continue
            else:
                get_lesson_list(course)
        else:
            get_lesson_list(course)
    except Exception as e:
        print(traceback.format_exc())
        print(f"Failed to parse {course['name']}", file=sys.stderr)
