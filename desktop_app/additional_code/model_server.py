import socket
import threading
import pickle
import cv2
import numpy as np
from ultralytics import YOLO


class NeuralNetServer:
    def __init__(self, host='127.0.0.1', port=5000, max_clients=5):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_clients)
        self.model = YOLO("C:\\Users\\soya.ivan\\PycharmProjects\\test_neural_network\\trained_models\\PyTorch\\varan_11s.pt")

        print(f"Запущена модель {self.model.model_name}\n"
              f"Классы модели: {self.model.names}")

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
                img_encoded = pickle.loads(data)

                image = cv2.imdecode(img_encoded, cv2.IMREAD_COLOR)
                print(f"Запуск инференса на изображении размером: {image.shape[0]}x{image.shape[1]} пикселей")

                # Запускаем инференс
                results = self.model(image)
                detections = results[0].boxes.xywh.cpu().numpy()

                # Преобразуем результаты в формат (id класса, x, y, width, height, res_w, res_h)
                processed_results = []
                for det in detections:
                    class_id = int(det[5])
                    x1, y1, width, height = det[:4]
                    res_w, res_h = image.shape[1], image.shape[0]
                    processed_results.append((class_id, x1, y1, width, height, res_w, res_h))

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
