import cv2
import time

import numpy as np
import math
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator

W = 640
H = 640
FPS = 30

class_color = {
    0: (255, 20, 147),
    1: (127, 255, 0),
    2: (0, 250, 154),
    3: (34, 139, 34),
    4: (32, 178, 170),
    5: (255, 255, 0),
    6: (255, 140, 0),
    7: (255, 0, 255),
    8: (0, 0, 255),
    9: (0, 255, 255),
    10: (47, 79, 79),
    11: (218, 165, 32),
    12: (255, 255, 255),
}

def get_color(id_class, dict_color):
    if id_class in dict_color.keys():
        return dict_color[id_class]
    else:
        return dict_color[sorted(dict_color.keys())[-1]]

def main():
    # Load a model
    #model = YOLO("trained_models/PyTorch/8s_correct_multiclass.pt")
    model = YOLO("../trained_models/PyTorch/varan_s.pt")
    class_names = model.names

    font = cv2.FONT_HERSHEY_SIMPLEX

    #cap = cv2.VideoCapture("E:/neural_networks/train_video/NVR_ch1_main_20240722123000_20240722124000.mp4")
    cap = cv2.VideoCapture("E:/Картинки с тракторов/Временная папка для создания видео/test_video.mp4")

    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Функция для ползунка
    def on_change(trackbar_value):
        cap.set(cv2.CAP_PROP_POS_FRAMES, trackbar_value)
        err, img = cap.read()
        img.resize(W, H)
        cv2.imshow('Video Process', img)
        pass

    cv2.namedWindow('Video Process')
    cv2.createTrackbar('Frame', 'Video Process', 0, length, on_change)

    prev_frame_time = 0

    while cap.isOpened():

        ret, frame = cap.read()

        if not ret:
            print("Frame didn't read!")
            break

        frame = cv2.resize(frame, (H, W))

        annotator = Annotator(frame)

        result = model.predict(frame, imgsz=640)[0]

        conf_list = result.boxes.conf.cpu().tolist()
        boxes = result.boxes.xyxy.cpu().tolist()
        d_classes = result.boxes.cls.cpu().tolist()

        for box, d_class, conf in zip(boxes, d_classes, conf_list):
            label_conf = round(conf, 1)
            annotator.box_label(
                box=box,
                label=class_names[int(d_class)] + " " + str(label_conf),
                color=get_color(int(d_class), class_color),
            )
            print(int(d_class), *box)

        new_frame_time = time.time()
        fps = 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time

        fps = int(fps)

        fps_color = [0, 255, 0] if fps > 30 else ([0, 255, 255] if fps > 15 else [0, 0, 255])
        cv2.putText(frame, "FPS:" + str(fps), [25, W - 25], font, 1, fps_color, 3, cv2.LINE_AA)

        cv2.imshow('Video Process', frame)

        k = cv2.waitKey(10)
        if k == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

