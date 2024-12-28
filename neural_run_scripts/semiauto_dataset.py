import cv2
import time
import os

import numpy as np
import math

from jupyterlab.semver import valid
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator

W = 640
H = 640

# Как много будет использовано картинок из пути
usage_percentage = 0.2
# Процент от картинок, которые пойдут в valid, все остальные в train
valid_percentage = 0.15

weights_path = "../trained_models/PyTorch/varan_s.pt"

images_path = "E:/Картинки с тракторов"
dir_name = "6_varan_kr4883-081"

dataset_path = "E:/neural_networks/Обучение Варана/Самообучение"
iterator_file = os.path.join(dataset_path, "iterator.txt")
viewed = os.path.join(dataset_path, "viewed")

dataset = os.path.join(dataset_path, "data.yaml")
train_path = os.path.join(dataset_path, "train")
valid_path = os.path.join(dataset_path, "valid")
test_path = os.path.join(dataset_path, "test")

class_color = {
    0: (255, 20, 147),
    1: (127, 255, 0),
    2: (0, 250, 154),
    3: (34, 139, 34),
    4: (32, 178, 170),
    5: (255, 255, 0),
    6: (255, 140, 0),
    7: (255, 0, 255),
    8: (0, 0, 255),
    9: (0, 255, 255),
    10: (47, 79, 79),
    11: (218, 165, 32),
    12: (255, 255, 255),
}

def get_color(id_class, dict_color):
    if id_class in dict_color.keys():
        return dict_color[id_class]
    else:
        return dict_color[sorted(dict_color.keys())[-1]]

def read_integer_from_file(file_path):
    try:
        with open(file_path, 'w') as file:
            # Считываем строку и преобразуем её в целое число
            line = file.readline().strip()
            return int(line)
    except ValueError:
        print("Ошибка: Файл не содержит валидного целого числа.")
        return -1
    except FileNotFoundError:
        print(f"Ошибка: Файл {file_path} не найден.")
        return -2

def get_images_from_folder(folder_path):
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp')
    return [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]

def get_images_names_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        with open(file_path, 'w'):
            pass
        return []

def remove_duplicates(source_list, comparison_list):
    return [item for item in source_list if item not in comparison_list]


def letterbox_resize(image, target_size):
    h, w, _ = image.shape
    target_w, target_h = target_size

    # Масштабируем изображение так, чтобы оно вписалось в target_size, сохраняя пропорции
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    # Изменяем размер изображения
    resized_image = cv2.resize(image, (new_w, new_h))

    # Создаем новое изображение с нужным размером и черным фоном
    new_image = np.zeros((target_h, target_w, 3), dtype=np.uint8)

    # Размещаем изменённое изображение в центре
    top_left_x = (target_w - new_w) // 2
    top_left_y = (target_h - new_h) // 2
    new_image[top_left_y:top_left_y + new_h, top_left_x:top_left_x + new_w] = resized_image

    return new_image

def main():
    model = YOLO(weights_path)
    class_names = model.names

    font = cv2.FONT_HERSHEY_SIMPLEX

    iterator = read_integer_from_file(iterator_file)
    if iterator == -1:
        print("Enter iterator number in file!")

    viewed_images = get_images_names_from_file(os.path.join(viewed, dir_name) + ".txt")

    current_train_images = get_images_from_folder(os.path.join(images_path, dir_name))
    current_train_images = remove_duplicates(current_train_images, viewed_images)

    cv2.namedWindow('Live Creation Dataset')

    f_viewed_txt = open(os.path.join(viewed, dir_name) + ".txt", 'a')

    while len(current_train_images) > 0:
        image = current_train_images[0]

        frame  = cv2.imread(image)

        if frame is None:
            print("Cannot open ", image, ", skipped!")
            continue

        frame = letterbox_resize(frame, (W, H))

        show_frame = frame.copy()

        annotator = Annotator(show_frame)

        result = model.predict(frame)[0]

        conf_list = result.boxes.conf.cpu().tolist()
        boxes = result.boxes.xyxy.cpu().tolist()
        d_classes = result.boxes.cls.cpu().tolist()

        for box, d_class, conf in zip(boxes, d_classes, conf_list):
            label_conf = round(conf, 1)
            annotator.box_label(
                box=box,
                label=class_names[int(d_class)] + " " + str(label_conf),
                color=get_color(int(d_class), class_color),
            )

        cv2.imshow('Live Creation Dataset', show_frame)

        key = cv2.waitKey(0)
        if key == ord('q'):
            print("Завершение создания датасета!")
            break
        elif key == ord('1'):
            print("Сохранение изображения ", image, "в тренировочный набор!")
            current_train_images = current_train_images[1:]
            f_viewed_txt.write(image + "\n")
            with open(os.path.join(train_path, image) + ".txt", "w") as file_t:


            continue
        elif key == ord('2'):
            print("Сохранение изображения ", image, "в валидационный набор!")
            current_train_images = current_train_images[1:]
            f_viewed_txt.write(image + "\n")
            continue
        elif key == ord('3'):
            print("Обновление изображения ", image, "!")
            continue
        else:
            continue

    f_viewed_txt.close()

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

