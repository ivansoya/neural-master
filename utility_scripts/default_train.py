import ultralytics
from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO(r"C:\Users\1\Documents\PycharmProjects\neural-master\untrained\yolov11\yolo11n.pt")

    # Обучение
    results = model.train(
        data=r"C:\Users\1\Documents\Проект Варан\СИЗ\data.yaml",
        epochs=100,
        imgsz=640,
        device=0,
        batch=64,
        # optimizer="AdamW"
        # lrf=0.2,
        # weight_decay=0.0001
        project=r"C:\Users\1\Documents\Проект Варан\Обучение\Запуски",  # своя папка
        name="yolov11_siz"  # имя подпапки
    )