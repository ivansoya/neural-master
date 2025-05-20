import socket
import threading
import pickle
import cv2
import numpy as np
from ultralytics import YOLO
from rknn.api import RKNN


class NeuralNetServer:
    def __init__(self, host='192.168.200.67', port=5000, max_clients=5):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_clients)
        self.model = YOLO("/var/local/annotation-server/25.03.2025")

        print(f"Запущена модель {self.model.model_name}\n")

    def handle_client(self, client_socket):
        try:
            while True:
                # Получаем размер входных данных
                data_size = client_socket.recv(4)
                if not data_size:
                    break
                data_size = int.from_bytes(data_size, 'big')
                print(f"Получен размер данных: {data_size} байт")

                # Получаем входные данные
                data = b''
                while len(data) < data_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        break
                    data += packet

                # Десериализация
                print([data[i] for i in range(len(data))])
                image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if image is None or image.size == 0:
                    print("Ошибка: изображение пустое или не загружено!")
                    continue
                cv2.imshow("Display Image", image)
                cv2.waitKey(0)
                print(f"Запуск инференса на изображении размером: {image.shape[1]}x{image.shape[0]} пикселей")
                # Запускаем инференс
                results = self.model(image)
                boxes = results[0].boxes

                # Преобразуем результаты в формат (id класса, x, y, width, height, res_w, res_h)
                processed_results = []
                for box in boxes:
                    class_id = int(box.cls)
                    x, y, width, height = box.xywh[0].tolist()
                    res_w, res_h = image.shape[1], image.shape[0]
                    processed_results.append((class_id, x, y, width, height, res_w, res_h))

                print(f"Найдено {len(processed_results)} объектов на изображении")

                # Отправляем результат обратно клиенту
                response_data = pickle.dumps(processed_results)
                response_size = len(response_data)
                print(f"Отправка результатов: {response_size} байт")
                client_socket.sendall(response_size.to_bytes(4, 'big') + response_data)

        except Exception as e:
            print(f"Ошибка обработки клиента: {e}")
        finally:
            client_socket.close()

    def start(self):
        print(f"Сервер запущен на {self.host}:{self.port}, ожидаем подключения...")
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Подключен клиент: {addr}")
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()


if __name__ == "__main__":
    server = NeuralNetServer()
    server.start()
