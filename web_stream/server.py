from flask import Flask, Response, render_template
import time
import requests

app = Flask(__name__)

# Список URL для видео потоков
video_urls = [
    "https://http.1voran.keenetic.link/current.jpg",
    "https://http.2voran.keenetic.link/current.jpg",
    "https://http.3voran.keenetic.link/current.jpg",
    "https://http.4voran.keenetic.link/current.jpg",
    "https://http.5voran.keenetic.link/current.jpg",
    "https://http.6voran.keenetic.link/current.jpg",
    "https://http.7voran.keenetic.link/current.jpg",
    "https://http.8voran.keenetic.link/current.jpg",
    "https://http.9voran.keenetic.link/current.jpg",
    "https://http.10voran.keenetic.link/current.jpg",
    "https://http.11voran.keenetic.link/current.jpg",
    "https://http.12voran.keenetic.link/current.jpg",
    "https://http.13voran.keenetic.link/current.jpg",
    "https://http.14voran.keenetic.link/current.jpg",
]

# Функция для генерации видео потока
def generate_video_stream(url):
    headers = {
        "User-Agent": "Mozilla/5.0",  # Некоторые камеры требуют заголовок
        "Accept": "multipart/x-mixed-replace"
    }

    try:
        response = requests.get(url, stream=True, headers=headers)

        if response.status_code != 200:
            print(f"Ошибка {response.status_code} при подключении к {url}")
            return

        boundary = None

        # Ищем boundary в заголовках (обычно: '--frame' или другой)
        content_type = response.headers.get("Content-Type", "")
        if "boundary=" in content_type:
            boundary = content_type.split("boundary=")[-1].encode()

        # Читаем и передаем поток в браузер
        for chunk in response.iter_content(chunk_size=1024):
            if boundary and boundary in chunk:  # Обнаружен новый кадр
                yield chunk  # Передаем весь кадр без изменений

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении видео потока: {e}")

# Маршрут для отображения видео
@app.route('/video_feed/<int:video_id>')
def video_feed(video_id):
    url = video_urls[video_id]
    return Response(generate_video_stream(url),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Главная страница
@app.route('/')
def index():
    video_list = list(enumerate(video_urls))  # Создаем список кортежей (индекс, URL)
    return render_template('index.html', video_list=video_list)

if __name__ == '__main__':
    app.run(debug=True)