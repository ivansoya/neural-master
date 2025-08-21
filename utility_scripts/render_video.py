from ultralytics import YOLO
import cv2
import sys

# Путь к модели и видео
model_path = r"C:\Users\1\Documents\Проект Варан\Обучение\Обученные модели\2025.08.21\varan_11n_adam_yaml.pt"  # или ваша обученная модель
input_video_path = r"C:\Users\1\Documents\Проект Варан\Запись с камер\4885 Открябрьск\4885_bucket_sleepers.mp4"
output_video_path = r"C:\Users\1\Documents\Проект Варан\Видео работы\4885_bucket_sleepers.mp4"

# Загружаем модель
model = YOLO(model_path)

# Открываем видео
cap = cv2.VideoCapture(input_video_path)
if not cap.isOpened():
    print("Не удалось открыть видео:", input_video_path)
    sys.exit(1)

# Получаем параметры видео
fps = int(cap.get(cv2.CAP_PROP_FPS))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Создаем объект записи видео
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Для .mp4
out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

print(f"Начинаем обработку {frame_count} кадров...")

# Обработка кадров
for i in range(frame_count):
    ret, frame = cap.read()
    if not ret:
        break

    # Обработка кадра моделью YOLO
    results = model.predict(frame, verbose=False)
    result_frame = results[0].plot()  # Получаем изображение с аннотациями

    # Запись кадра в новый видеофайл
    out.write(result_frame)

    # Прогресс
    progress = (i + 1) / frame_count * 100
    print(f"\rОбработано кадров: {i + 1}/{frame_count} ({progress:.2f}%)", end="")

print("\nОбработка завершена!")

# Освобождаем ресурсы
cap.release()
out.release()
cv2.destroyAllWindows()
