from ultralytics import YOLO
import cv2

# -----------------------------
# Параметры
# -----------------------------
MODEL_PATH = r"C:\Users\1\Documents\Проект Варан\Обучение\Обученные модели\2025.08.28\varan11n_sgd_12c.pt"  # путь к твоей модели YOLOv8
VIDEO_PATH = r"C:\Users\1\Documents\Проект Варан\Запись с камер\5192 Санкт-Петербург\video_segment_2025-08-21--13-24-05.mp4"       # входное видео
CONF_THRESH = 0.25                    # порог confidence
SCALE_FACTOR = 0.5  # уменьшение окна до 50%

# -----------------------------
# Загружаем модель
# -----------------------------
model = YOLO(MODEL_PATH)

# -----------------------------
# Видео
# -----------------------------
cap = cv2.VideoCapture(VIDEO_PATH)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# -----------------------------
# Инференс по кадрам
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model.predict(frame, conf=CONF_THRESH)[0]  # результат YOLOv8
    boxes = results.boxes.xyxy.cpu().numpy()            # [x1, y1, x2, y2]
    scores = results.boxes.conf.cpu().numpy()          # confidence
    class_ids = results.boxes.cls.cpu().numpy()        # class

    # Рисуем рамки
    for box, score, cls_id in zip(boxes, scores, class_ids):
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
        cv2.putText(frame, f"{int(cls_id)}:{score:.2f}", (x1, y1-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

    small_frame = cv2.resize(frame, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
    cv2.imshow("YOLOv8 Video", small_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
