if __name__ == "__main__":
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.data.split import autosplit

    # Проверка среды
    ultralytics.checks()

    # Входные данные
    dataset_path = r"C:\Users\1\Documents\Проект Варан\Обучение\Датасеты\2025.08.21\labeled_images"

    # Выполняем autosplit, он возвращает список с путями к изображениям
    autosplit(
        path=dataset_path,
        weights=(0.8, 0.2, 0.0),
        annotated_only=False,
    )

    # Загружаем модель
    model = YOLO(r"C:\Users\1\Documents\Проект Варан\Обучение\Модели\yolov11\yolo11n.pt")

    # Обучение
    results = model.train(
        data=r"C:\Users\1\Documents\Проект Варан\Обучение\Датасеты\2025.08.21\data.yaml",
        epochs=100,
        imgsz=640,
        device=0,
        batch=64,
        #optimizer="AdamW"
        # lrf=0.2,
        # weight_decay=0.0001
        project=r"C:\Users\1\Documents\Проект Варан\Обучение\Запуски",  # своя папка
        name="run_2025_08_21_sgd_yolo11n"  # имя подпапки
    )
