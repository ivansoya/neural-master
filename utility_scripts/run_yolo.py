import cv2
from ultralytics import YOLO

# === Настройки ===
model_path = r"C:\Users\1\Documents\PycharmProjects\neural-master\trained_models\PPE\yolo_11sz.pt"       # веса модели (замени на свои)
image_path = r"C:\Users\1\Documents\Проект Варан\Буклеты\СИЗ\KZT_1_SPB_2025-06-20--13-32-07.jpg"             # входное изображение
output_path = r"C:\Users\1\Documents\Проект Варан\Буклеты\СИЗ\KZT_1_SPB_2025-06-20--13-32-07_pred.jpg"       # сохранённое изображение
excluded_classes = {"ear", "ear-mufs", "face", "face-guard", "face-mask", "foot", "tool", "glasses", "medical-suit", "shoes", "safety-suit", "safety-vest"}    # классы, которые не отображаем

blue_classes = {"person"}
green_classes = {"helmet", "vest", "gloves"}          # рисуем зелёным
red_classes = {"no_helmet", "no_vest", "hands"}      # рисуем красным

# === Загрузка модели ===
model = YOLO(model_path)

# === Запуск предсказания ===
results = model(image_path, conf=0.25, verbose=False)  # conf = порог уверенности

# === Чтение исходного изображения ===
img = cv2.imread(image_path)

# === Отрисовка результатов ===
for r in results:
    for box in r.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        conf = float(box.conf[0])

        # Пропускаем исключённые классы
        if cls_name in excluded_classes:
            continue

        # Координаты bbox
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        if cls_name in green_classes:
            color = (0, 255, 0)  # зелёный
        elif cls_name in red_classes:
            color = (0, 0, 255)  # красный
        else:
            color = (255, 0, 0)  # синий (по умолчанию)

        # Рисуем прямоугольник
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

        # Подписываем класс + уверенность
        label = f"{cls_name} {conf:.2f}"
        cv2.putText(img, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

# === Сохраняем изображение ===
cv2.imwrite(output_path, img)

print(f"Результат сохранён в {output_path}")