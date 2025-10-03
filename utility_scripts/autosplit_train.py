if __name__ == "__main__":
    import random
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
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

    clean_aug = A.Compose([
        ToTensorV2()
    ], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]))

    aug1 = A.Compose([
        A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), p=0.2),
        A.GaussNoise(std_range=(0.1, 0.2), p=0.75),
        A.MotionBlur(blur_limit=(14, 22), angle_range=(0, 90), direction_range=(-0.5, 0.5), p=0.4),
        A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=0.5),
        A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1), kernel_size=5, sigma=1, p=1),
        A.Defocus(radius=(3, 10), alias_blur=(0.1, 0.5), p=0.25)
    ], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]))

    aug2 = A.Compose([
        A.CLAHE(p=0.3),
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=1),
        A.Erasing(scale=(0.02, 0.3), ratio=(0.3, 3.3), p=0.3),
        A.BBoxSafeRandomCrop(erosion_rate=0.1, p=0.3),
        A.SafeRotate(limit=(-90, 90), p=0.2),
    ], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]))

    augs_dict = {
        "clean": clean_aug,
        "aug1": aug1,
        "aug2": aug2
    }

    def random_aug(image, bboxes, labels):
        aug = random.choice(list(augs_dict.values()))
        return aug(image=image, bboxes=bboxes, class_labels=labels)

    # Загружаем модель
    model = YOLO(r"C:\Users\1\Documents\Проект Варан\Обучение\Модели\yolov11\yolo11n.pt")

    # Обучение
    results = model.train(
        data=r"C:\Users\1\Documents\Проект Варан\Обучение\Датасеты\2025.08.21\data.yaml",
        epochs=200,
        imgsz=640,
        device=0,
        batch=64,
        project=r"C:\Users\1\Documents\Проект Варан\Обучение\Запуски",  # своя папка
        name="run_2025_10_2_sgd_aug_custom_yolo11n",  # имя подпапки
        transform = random_aug
    )


