import multiprocessing
import time
from statistics import pvariance
from typing import Dict, Any, List
import numpy as np
from flask import Flask, render_template, Response, request, redirect, url_for
import socket
import cv2
from datetime import datetime
from hexss import json_load, json_update, dict_to_manager_dict
import platform
import logging
import signal
import sys

# Conditional imports based on the platform
if platform.system() == "Windows":
    import mss
else:
    mss = None

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def display_capture(data: Dict[str, Any]) -> None:
    if platform.system() != "Windows":
        logging.warning("Display capture is only supported on Windows.")
        return

    with mss.mss() as sct:
        while True:
            try:
                screenshot = sct.grab(sct.monitors[0])
                image = np.array(screenshot)
                data['display_capture'] = image
            except Exception as e:
                logging.error(f"Error in display capture: {e}")
                time.sleep(1)


def video_capture(data: Dict[str, Any], camera_id: int) -> None:
    def setup() -> cv2.VideoCapture:
        cap = cv2.VideoCapture(camera_id)
        cap.set(3, data['camera'][camera_id]['width_height'][0])
        cap.set(4, data['camera'][camera_id]['width_height'][1])
        data['camera'][camera_id]['width_height_from_cap'] = [int(cap.get(3)), int(cap.get(4))]
        return cap

    cap = setup()
    while True:
        try:
            if data['camera'][camera_id]['setup']:
                data['camera'][camera_id]['setup'] = False
                cap.release()
                cap = setup()

            if data['camera'][camera_id]['camera_enabled']:
                status, img = cap.read()
                data['camera'][camera_id]['status'] = status
                if status:
                    data['camera'][camera_id]['img'] = img.copy()
                else:
                    logging.warning(f"Failed to capture image from camera {camera_id}")
                    time.sleep(1)
                    cap.release()
                    cap = setup()
            else:
                data['camera'][camera_id]['status'] = False
                data['camera'][camera_id]['img'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
        except Exception as e:
            logging.error(f"Error in video capture for camera {camera_id}: {e}")
            time.sleep(1)


def get_data(data: Dict[str, Any], source: str, camera_id: int, quality=100) -> np.ndarray:
    if source == 'video_capture':
        frame = data['camera'][camera_id]['img']
        status = data['camera'][camera_id]['status']
        if not status:
            frame = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
            cv2.putText(frame, f'Failed to capture image', (30, 50), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, f'from camera {camera_id}', (30, 90), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (30, 130), 1, 2, (0, 0, 255), 2)
    else:  # source == 'display_capture':
        frame = data['display_capture']
    if quality == 100:
        ret, buffer = cv2.imencode('.jpg', frame)
    else:
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]  # Adjust quality (0-100)
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


@app.route('/')
def index():
    data = app.config['data']
    camera_states = [
        {
            'camera_enabled': data['camera'][camera_id]['camera_enabled'],
            'width': data['camera'][camera_id]['width_height_from_cap'][0],
            'height': data['camera'][camera_id]['width_height_from_cap'][1]
        } for camera_id in range(len(data['camera']))
    ]
    return render_template('index.html', camera_states=camera_states)


@app.route('/update_cameras', methods=['POST'])
def update_cameras():
    data = app.config['data']
    for camera_id in range(len(data['camera'])):
        camera_key = f'camera_{camera_id}'
        data['camera'][camera_id]['camera_enabled'] = camera_key in request.form
        width = request.form.get(f'w{camera_key}')
        height = request.form.get(f'h{camera_key}')
        if width and height:
            data['camera'][camera_id]['width_height'] = [int(width), int(height)]
            data['camera'][camera_id]['width_height_from_cap'] = [None, None]
            data['camera'][camera_id]['setup'] = True

            # update config file
            config = json_load('config.json')
            config['camera'][camera_id]['width_height'] = [int(width), int(height)]
            json_update('config.json', config)

    return redirect(url_for('index'))


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    quality = request.args.get('quality', default=100, type=int)
    buffer = get_data(app.config['data'], source, camera_id, quality)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/video')
def get_video():
    source = request.args.get('source', default='display_capture', type=str)
    camera_id = request.args.get('id', default=0, type=int)
    quality = request.args.get('quality', default=30, type=int)

    def generate():
        while True:
            buffer = get_data(app.config['data'], source, camera_id, quality)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data: Dict[str, Any]) -> None:
    log = logging.getLogger('werkzeug')
    log.disabled = True
    app.config['data'] = data
    ipv4 = data['ipv4']
    port = data['port']
    logging.info(f"Running on http://{ipv4}:{port}")
    app.run(host=ipv4, port=port, debug=False, use_reloader=False)


def signal_handler(signum, frame):
    logging.info("Received signal to terminate. Shutting down...")
    sys.exit(0)


def main():
    multiprocessing.freeze_support()
    manager = multiprocessing.Manager()
    config = json_load('config.json', {
        "ipv4": "auto",
        "port": 2000,
        "camera": [
            {
                "width_height": [640, 480]
            }
        ]
    })
    json_update('config.json', config)
    data = dict_to_manager_dict(manager, config)
    if data['ipv4'] == 'auto':
        hostname = socket.gethostname()
        data['ipv4'] = socket.gethostbyname(hostname)

    for camera_id in range(len(data['camera'])):
        data['camera'][camera_id]['status'] = False
        data['camera'][camera_id]['img'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
        data['camera'][camera_id]['camera_enabled'] = True  # Default to enabled
        data['camera'][camera_id]['width_height_from_cap'] = [None, None]
        data['camera'][camera_id]['setup'] = False
    data['display_capture'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)

    processes: List[multiprocessing.Process] = [
        multiprocessing.Process(target=video_capture, args=(data, camera_id))
        for camera_id in range(len(data['camera']))
    ]
    processes.append(multiprocessing.Process(target=display_capture, args=(data,)))
    processes.append(multiprocessing.Process(target=run_server, args=(data,)))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    for process in processes:
        process.start()

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Terminating processes...")
    finally:
        for process in processes:
            process.terminate()
            process.join()


if __name__ == "__main__":
    main()
