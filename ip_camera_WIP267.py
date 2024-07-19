import cv2
import numpy as np
import requests
from requests.auth import HTTPDigestAuth

username = 'admin'
password = 'A00000000'
ip = "192.168.1.108"


def find_url():
    url_options = [
        f"rtsp://{username}:{password}@{ip}:554/live",
        f"rtsp://{username}:{password}@{ip}:554/h264",
        f"rtsp://{username}:{password}@{ip}:554/mpeg4",
        f"rtsp://{username}:{password}@{ip}:554/ch01/0",
        f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
        f"http://{username}:{password}@{ip}/video.cgi",
        f"http://{username}:{password}@{ip}/mjpg/video.mjpg"
    ]

    for url in url_options:
        print(f"Trying URL: {url}")
        cap = cv2.VideoCapture(url)
        ret, frame = cap.read()
        if ret:
            print(f"Success with URL: {url}")
        cap.release()


def get_video():
    # url = f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"
    url = f"rtsp://{username}:{password}@{ip}:554/live"
    cap = cv2.VideoCapture(url)

    while True:
        ret, frame = cap.read()
        cv2.imshow('IP Camera', cv2.resize(frame, (0, 0), fx=0.5, fy=0.5))
        cv2.waitKey(1)


def get_image():
    # Image URL
    image_url = f"http://{ip}/cgi-bin/snapshot.cgi"

    # Create a session to persist the authentication
    session = requests.Session()
    session.auth = HTTPDigestAuth(username, password)

    while True:
        try:
            response = session.get(image_url)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            image_array = np.frombuffer(response.content, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            if frame is not None:
                resized_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                cv2.imshow('IP Camera', resized_frame)
            else:
                print("Failed to decode image")

        except requests.RequestException as e:
            print(f"Failed to retrieve image: {str(e)}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

        cv2.waitKey(1)


if __name__ == "__main__":
    # find_url()
    get_video()
    # get_image()
