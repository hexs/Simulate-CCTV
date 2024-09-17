from datetime import datetime
import cv2
import urllib.request
import numpy as np


def get_from_image():
    url = 'http://192.168.137.212:2000/image?source=video_capture&id=0'
    while True:
        t1 = datetime.now()
        req = urllib.request.urlopen(url)
        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        img = cv2.imdecode(arr, -1)
        t2 = datetime.now()
        print((t2 - t1).total_seconds())
        cv2.imshow('Image from URL', img)
        cv2.waitKey(1)


def get_from_video():
    url = 'http://192.168.225.137:2000/old-video'
    cap = cv2.VideoCapture(url)
    while True:
        _, img = cap.read()
        cv2.imshow('Video from URL', img)
        cv2.waitKey(1)


if __name__ == '__main__':
    get_from_image()
    # get_from_video()
