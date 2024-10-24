import os
import sys

import argparse
import time

import ffmpeg
from dirsearch.lib.core.settings import OUTPUT_FORMATS

parser = argparse.ArgumentParser(add_help=False)

parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit")
parser.add_argument("-c", "--session-cookie", help="Session Cookie", required=False)
parser.add_argument("-y", "--ykt-host", help="RainClassroom Host", required=False, default="pro.yuketang.cn")

args = parser.parse_args()

if args.help:
    print("""RainClassroom Video Downloader

requirements:
    - Python >= 3.12
    - requests
    - websocket-client
    - qrcode
    - ffmpeg-python
""")

    print(parser.format_help())

    exit()

import requests
import websocket
import json
import qrcode

# --- --- --- Section LOGIN --- --- --- #
# Login to RainClassroom
userinfo = {}
rainclassroom_sess = requests.session()

YKT_HOST = args.ykt_host
DOWNLOAD_FOLDER = "data"
CACHE_FOLDER = "cache"


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


if args.session_cookie is not None:
    rainclassroom_sess.cookies['sessionid'] = args.session_cookie

else:
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

# --- --- --- Section Get Course List --- --- --- #

# 获取自己的课程列表
shown_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/courses/list?identity=2").json()

hidden_courses = rainclassroom_sess.get(f"https://{YKT_HOST}/v2/api/web/classroom_archive").json()

courses = shown_courses['data']['list'] + hidden_courses['data']['classrooms']

rainclassroom_sess.cookies['xtbz'] = 'ykt'


# --- --- --- Section Get Lesson List --- --- --- #
# {
#     "university_name": "",
#     "term": 202401,
#     "university_logo_pic": "",
#     "name": "NAME",
#     "type_count": [],
#     "students_count": 7,
#     "color_system": 3,
#     "course": {
#         "update_time": "",
#         "name": "",
#         "admin_id": 0,
#         "university_id": 0,
#         "type": 0,
#         "id": 0
#     },
#     "teacher": {
#         "user_id": 0,
#         "name": "",
#         "avatar": ""
#     },
#     "create_time": "",
#     "university_id": 0,
#     "time": "",
#     "course_id": 0,
#     "university_logo": "0",
#     "university_mini_logo": "0",
#     "id": 0,
#     "is_pro": true,
#     "color_code": 0
# }


def get_lesson_list(course: dict, name_prefix: str = ""):
    lesson_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/v2/api/web/logs/learn/{course['classroom_id']}?actype=14&page=0&offset=500&sort=-1").json()

    os.makedirs(f"{DOWNLOAD_FOLDER}/{course['name']}", exist_ok=True)
    os.makedirs(f"{CACHE_FOLDER}/{course['name']}", exist_ok=True)
    name_prefix += course['name'] + "/"

    l = len(lesson_data['data']['activities'])

    for index, lesson in enumerate(lesson_data['data']['activities']):
        # Lesson
        try:
            download_lesson(lesson, name_prefix + str(l - index))
        except Exception as e:
            print(e)
            print(f"Failed to download {name_prefix} - {lesson['title']}", file=sys.stderr)


# --- --- --- Section Download Lesson --- --- --- #
# {
#      "type": 14,
#      "id": 7153416,
#      "courseware_id": "909642544544463488",
#      "title": "R8-三相-周期非正弦",
#      "create_time": 1686274642000,
#      "attend_status": true,
#      "is_finished": true
# }


def download_lesson(lesson: dict, name_prefix: str = ""):
    lesson_video_data = rainclassroom_sess.get(
        f"https://{YKT_HOST}/api/v3/lesson-summary/replay?lesson_id={lesson['courseware_id']}").json()
    name_prefix += "-" + lesson['title']

    if 'live' not in lesson_video_data['data']:
        print(f"Skipping {name_prefix} - No Video", file=sys.stderr)
        return

    has_error = False

    for order, segment in enumerate(lesson_video_data['data']['live']):
        # Segment
        try:
            download_segment(segment['url'], order, name_prefix)
        except Exception as e:
            print(e)
            print(f"Failed to download {name_prefix} - {segment['order']}", file=sys.stderr)
            has_error = True

    if not has_error and len(lesson_video_data['data']['live']) > 0:
        print(f"Concatenating {name_prefix}")

        with open(f"{CACHE_FOLDER}/concat.txt", "w") as f:
            f.write("\n".join(
                [f"file '{name_prefix}-{i}.mp4'" for i in range(len(lesson_video_data['data']['live']))]
            ))

        cmd = f"ffmpeg -f concat -safe 0 -hwaccel cuda -hwaccel_output_format cuda -i {CACHE_FOLDER}/concat.txt -c:v hevc_nvenc -b:v 200k -maxrate 400k -bufsize 3200k -r 8 -rc-lookahead 1024 -c:a copy -rematrix_maxval 1.0 -ac 1 '{DOWNLOAD_FOLDER}/{name_prefix}.mp4' -n"

        print(cmd)
        os.system(cmd)

    if has_error:
        with open(f"{DOWNLOAD_FOLDER}/error.log", "a") as f:
            f.write(f"{name_prefix}\n")


# --- --- --- Section Download Segment --- --- --- #
# {
#     "id": "743834725938342272",
#     "code": "kszt_DdQU9sOod7o",
#     "type": 2,
#     "source": "th",
#     "url": "https://kszt-playback.xuetangx.com/gifshow-xuetangx/73466bdb387702307504996781/f0.mp4?auth_key=1729778852-4128559473511008914-0-e0c959d1504f92ef5a5d45000f46330d",
#     "start": 1666508813000,
#     "end": 1666510612000,
#     "duration": 1799000,
#     "hiddenStatus": 0,
#     "order": 0,
#     "replayOssStatus": 0,
#     "recordFileId": "",
#     "recordType": "",
#     "subtitlePath": ""
# }


def download_segment(url: str, order: int, name_prefix: str = ""):
    print(f"Downloading {name_prefix} - {order}")
    ret = os.system(
        f"aria2c -o '{CACHE_FOLDER}/{name_prefix}-{order}.mp4' -x 16 -s 16 '{url}' -c")
    if ret != 0:
        raise Exception(f"Failed to download {name_prefix}-{order}")


for course in courses:
    try:
        get_lesson_list(course)
    except Exception as e:
        print(e)
        print(f"Failed to download {course['name']}", file=sys.stderr)
