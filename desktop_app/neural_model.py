import json
from queue import Queue
import threading
import socket
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtGui import QColor
from ultralytics import YOLO

from PyQt5.QtCore import QThread, pyqtSignal, QObject, pyqtSlot, QTimer

from utility import FAnnotationClasses, FAnnotationData


class UBaseNeuralNet(QObject):
    signal_on_added = pyqtSignal(int)
    signal_on_result = pyqtSignal(int, list)

    def __init__(self, classes: FAnnotationClasses):
        super().__init__()
        self.model = None
        self.classes = classes
        self.image_queue: Queue[tuple[int, np.ndarray]] = Queue()
        self.index_uniques: set[int] = set()

        self.running = False
        self.processing = False

    def load_model(self, model_path: str):
        raise NotImplementedError

    def add_to_queue(self, index: int, image: np.ndarray):
        if index in self.index_uniques:
            return

        self.index_uniques.add(index)
        self.image_queue.put((index, image))
        self.signal_on_added.emit(index)

        if not self.processing:
            self.schedule_next()

    @pyqtSlot()
    def start_work(self):
        self.running = True

    def schedule_next(self):
        QTimer.singleShot(0, self.process_queue)

    @pyqtSlot()
    def process_queue(self):
        if not self.running:
            return

        if self.image_queue.empty():
            self.processing = False
            return

        self.processing = True

        index, image = self.image_queue.get()
        self.index_uniques.remove(index)
        result = self.process_image(image)
        self.signal_on_result.emit(index, result)

        self.schedule_next()

    def process_image(self, image: np.ndarray) -> list[FAnnotationData]:
        raise NotImplementedError

    def is_running(self) -> bool:
        return True if self.model else False

    def stop(self):
        self.running = False

class ULocalDetectYOLO(UBaseNeuralNet):
    def __init__(self, model_path, classes: FAnnotationClasses):
        super().__init__(classes)
        self.load_model(model_path)

    def load_model(self, model_path: str):
        self.model = YOLO(model_path)

    def process_image(self, image: np.ndarray):
        results = self.model(image)[0]  # Первый кадр
        detections: list[FAnnotationData] = list()
        count = 1
        for box in results.boxes:
            x, y, width, height = box.xywh[0].tolist()
            class_id = int(box.cls)
            #conf = box.conf

            res_h, res_w = image.shape[:2]
            class_name = self.classes.get_name(class_id)
            class_color = self.classes.get_color(class_id)
            detect_data = FAnnotationData(
                count,
                [x - width /2, y - height / 2, width, height],
                [],
                class_id,
                "Unresolved" if class_name is None else class_name,
                QColor("#606060") if class_color is None else class_color,
                int(res_w),
                int(res_h)
            )
            detections.append(detect_data)
            count += 1

        return detections if detections else []


class URemoteNeuralNet(UBaseNeuralNet):
    def __init__(self, classes: FAnnotationClasses, ip_address: str, port: int):
        super().__init__(classes)
        self.server_ip = ip_address
        self.server_port = port
        self.sock = None

    def is_running(self) -> bool:
        return self.connect_to_server()

    def connect_to_server(self):
        """ Подключение к серверу """
        if self.sock is not None:
            return True
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
                return []

        try:
            self.sock.settimeout(5)
            _, data = cv2.imencode('.jpg', image)
            self.sock.sendall(
                len(data).to_bytes(4, 'big') +
                data.tobytes()
            )
            print(f"Отправлено изображение размером {len(data)}")

            json_size = int.from_bytes(self.sock.recv(4), 'big')
            json_data_bytes = b""
            while len(json_data_bytes) < json_size:
                packet = self.sock.recv(json_size - len(json_data_bytes))
                if not packet:
                    print("Ошибка: соединение разорвано!")
                    return []
                json_data_bytes += packet

            result = self._process_detection_results(json_data_bytes.decode("utf-8"))
            print(f"Получен ответ от сервера: {result}")
            return result

        except socket.timeout:
            print("Превышен интервал ожидания 5 секунд!")
            return []
        except Exception as e:
            print(f"Ошибка при отправке/получении данных: {e}")
            if self.sock:
                self.sock.close()
                self.sock = None
            return []

    def _process_detection_results(self, response: str):
        annotation_data: list[FAnnotationData] = list()
        json_data = json.loads(response)
        if json_data:
            detections = json_data.get("detections", [])
            error_code = json_data.get("error_code", -1)

            if error_code < 0:
                return []
            try:
                detect_num = 1
                for i, object_d in enumerate(detections):
                    class_id = object_d['class_id']
                    class_color = self.classes.get_color(class_id)
                    class_name = self.classes.get_name(class_id)
                    ann_data = FAnnotationData(
                        detect_num,
                        [object_d['x'] - object_d['width'] / 2, object_d['y'] - object_d['height'] / 2,
                        object_d['width'], object_d['height']],
                        [],
                        class_id,
                        "Unresolved" if class_name is None else class_name,
                        QColor("#606060") if class_color is None else class_color,
                        int(object_d['resolution_w']),
                        int(object_d['resolution_h'])
                    )
                    annotation_data.append(ann_data)
                    detect_num += 1
                return annotation_data
            except Exception as error:
                print(str(error))
                return []
        else:
            return []

    def stop(self):
        """ Остановка потока и закрытие соединения """
        super().stop()
        if self.sock:
            self.sock.close()
            self.sock = None