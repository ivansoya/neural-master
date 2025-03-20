from queue import Queue
import threading
from typing import Union, Optional

import numpy as np
from PyQt5.QtGui import QColor
from ultralytics import YOLO

from PyQt5.QtCore import QThread, pyqtSignal

from utility import FAnnotationClasses, FDetectAnnotationData


class UBaseNeuralNet(QThread):
    signal_on_result = pyqtSignal(int, list)
    signal_on_added = pyqtSignal(int)
    signal_on_queue_empty = pyqtSignal()

    def __init__(self, classes: FAnnotationClasses):
        super().__init__()
        self.model = None
        self.classes = classes
        self.image_queue: Queue[tuple[int, np.ndarray]] = Queue()

        self.running = False
        self.queue_event = threading.Event()

    def load_model(self, model_path: str):
        raise NotImplementedError

    def add_to_queue(self, index: int, image: np.ndarray):
        self.image_queue.put(
            (index, image)
        )
        self.signal_on_added.emit(index)
        self.queue_event.set()

    def run(self):
        self.running = True

        while self.running:
            self.queue_event.wait()  # Блокировка, если очередь пуста

            while not self.image_queue.empty():
                index, image = self.image_queue.get()
                result = self.process_image(image)
                if result:
                    self.signal_on_result.emit(index, result)  # Отправляем результаты

            self.signal_on_queue_empty.emit()  # Очередь опустела
            self.queue_event.clear()  # Блокируем поток до следующего добавления

    def process_image(self, image: np.ndarray):
        """ Метод инференса (реализуется в наследниках) """
        raise NotImplementedError

    def is_running(self) -> bool:
        return True if self.model else False

    def stop(self):
        """ Остановка потока """
        self.running = False
        self.queue_event.set()  # Разблокируем поток перед завершением
        self.quit()
        self.wait()


class ULocalDetectYOLO(UBaseNeuralNet):
    def __init__(self, model_path, classes: FAnnotationClasses):
        super().__init__(classes)
        self.load_model(model_path)

    def load_model(self, model_path: str):
        self.model = YOLO(model_path)

    def process_image(self, image: np.ndarray):
        results = self.model(image)[0]  # Первый кадр
        detections: list[FDetectAnnotationData] = list()

        for box in results.boxes:
            x, y, width, height = box.xywh[0].tolist()
            class_id = int(box.cls)
            conf = box.conf

            res_w, res_h = image.shape[:2]
            class_name = self.classes.get_name(class_id)
            class_color = self.classes.get_color(class_id)
            detect_data = FDetectAnnotationData(
                int(x),
                int(y),
                int(width),
                int(height),
                class_id,
                "Unresolved" if class_name is None else class_name,
                QColor("#606060") if class_color is None else class_color,
                int(res_w),
                int(res_h)
            )
            detections.append(detect_data)

        print(f"{self.model.model_name} разметила изображение и получила следующие результаты: {[str(detect) for detect in detections]}")

        return detections if detections else None