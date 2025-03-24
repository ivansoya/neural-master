from queue import Queue
import threading
import socket
import pickle

import cv2
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

            res_h, res_w = image.shape[:2]
            class_name = self.classes.get_name(class_id)
            class_color = self.classes.get_color(class_id)
            detect_data = FDetectAnnotationData(
                int(x - width /2),
                int(y - height / 2),
                int(width),
                int(height),
                class_id,
                "Unresolved" if class_name is None else class_name,
                QColor("#606060") if class_color is None else class_color,
                int(res_w),
                int(res_h)
            )
            detections.append(detect_data)

        return detections if detections else None


class URemoteNeuralNet(UBaseNeuralNet):
    def __init__(self, classes: FAnnotationClasses, ip_address: str, port: int):
        super().__init__(classes)
        self.server_ip = ip_address
        self.server_port = port
        self.sock = None

    def is_running(self) -> bool:
        return True if self.sock else False

    def connect_to_server(self):
        """ Подключение к серверу """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.server_port))
            return True
        except socket.error as e:
            print(f"Ошибка подключения к серверу: {e}")
            self.sock = None
            return False

    def load_model(self, model_path: str):
        """ Переопределено, но не используется, так как модель работает удаленно """
        pass

    def process_image(self, image: np.ndarray):
        """ Отправка изображения на сервер и получение результата """
        if self.sock is None:
            if not self.connect_to_server():
                return None

        try:
            # Кодирование изображения в байты
            _, img_encoded = cv2.imencode('.jpg', image)
            data = pickle.dumps(img_encoded)
            size = len(data)

            # Отправка размера и данных
            self.sock.sendall(size.to_bytes(4, 'big') + data)

            # Получение ответа
            response_size = int.from_bytes(self.sock.recv(4), 'big')
            response_data = b''
            while len(response_data) < response_size:
                response_data += self.sock.recv(4096)

            # Десериализация ответа
            result = self._process_detection_results(pickle.loads(response_data))
            print(f"Получен ответ от сервера: {result}")
            return result

        except Exception as e:
            print(f"Ошибка при отправке/получении данных: {e}")
            self.sock = None
            return None

    def _process_detection_results(self, results: list[tuple]):
        detections: list[FDetectAnnotationData] = list()

        for annotation in results:
            class_id, x, y, width, height, res_w, res_h = annotation

            class_color = self.classes.get_color(class_id)
            class_name = self.classes.get_name(class_id)

            ann_data = FDetectAnnotationData(
                int(x - width / 2),
                int(y - height / 2),
                int(width),
                int(height),
                class_id,
                "Unresolved" if class_name is None else class_name,
                QColor("#606060") if class_color is None else class_color,
                int(res_w),
                int(res_h)
            )
            detections.append(ann_data)

        return detections


    def stop(self):
        """ Остановка потока и закрытие соединения """
        super().stop()
        if self.sock:
            self.sock.close()
            self.sock = None