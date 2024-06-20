import multiprocessing
from flask import Flask, render_template, Response
import socket
import cv2

app = Flask(__name__)


def capture(data):
    cap = cv2.VideoCapture(0)
    while True:
        status, img = cap.read()
        data['status'] = status
        if status:
            data['img'] = img.copy()
        else:
            cap = cv2.VideoCapture(0)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/image')
def get_image():
    frame = app.config['data']['img']
    success = app.config['data']['status']

    if success:
        ret, buffer = cv2.imencode('.jpg', frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    else:
        return "Failed to capture image", 500


def generate_video_stream(data, check_status=True):
    while True:
        frame = data['img']
        success = data['status']

        if check_status and success or check_status == False:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\nFailed to capture image\r\n')


@app.route('/video')
def video_feed():
    return Response(generate_video_stream(app.config['data']),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/old-video')
def old_video_feed():
    return Response(generate_video_stream(app.config['data'], check_status=False),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data):
    app.config['data'] = data
    hostname = socket.gethostname()
    ipv4_address = socket.gethostbyname(hostname)
    app.run(host=ipv4_address, port=2000, debug=True, use_reloader=False)


if __name__ == "__main__":
    manager = multiprocessing.Manager()
    data = manager.dict()

    capture_process = multiprocessing.Process(target=capture, args=(data,))
    run_server_process = multiprocessing.Process(target=run_server, args=(data,))

    capture_process.start()
    run_server_process.start()

    capture_process.join()
    run_server_process.join()
