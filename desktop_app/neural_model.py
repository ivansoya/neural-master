from queue import Queue
import threading
from typing import Union, Optional

import numpy as np
from ultralytics import YOLO

from PyQt5.QtCore import QThread, pyqtSignal


class UBaseNeuralNet(QThread):
    signal_on_result = pyqtSignal(int, tuple)
    signal_on_queue_empty = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.model = None
        self.image_queue: Queue[tuple[int, np.ndarray]] = Queue()

        self.running = False
        self.queue_event = threading.Event()

    def load_model(self, model_path: str):
        raise NotImplementedError

    def add_to_queue(self, index: int, image: np.ndarray):
        self.image_queue.put(
            (index, image)
        )
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

    def stop(self):
        """ Остановка потока """
        self.running = False
        self.queue_event.set()  # Разблокируем поток перед завершением
        self.quit()
        self.wait()


class ULocalYOLO(UBaseNeuralNet):
    def __init__(self, model_path):
        super().__init__()
        self.load_model(model_path)

    def load_model(self, model_path: str):
        self.model = YOLO(model_path)

    def process_image(self, image: np.ndarray):
        results = self.model(image)[0]  # Первый кадр
        detections = []

        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            class_id = int(box.cls)
            detections.append((class_id, int(x1), int(y1), int(x2 - x1), int(y2 - y1)))

        return detections if detections else None