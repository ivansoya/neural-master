import os.path
from typing import Optional

import yaml
import configparser
from enum import Enum

from PyQt5.QtCore import Qt, QPointF, QPoint, QRect
from PyQt5.QtGui import QColor

import random

from PyQt5.QtWidgets import QMessageBox

GColorList = [
    QColor(255, 0, 0),
    QColor(0, 255, 0),
    QColor(0, 0, 255),
    QColor(255, 255, 0),
    QColor(255, 0, 255),
    QColor(0, 255, 255),
]

class EWorkMode(Enum):
    DragMode = 1
    AnnotateMode = 2
    ForceDragMode = 3

class EAnnotationStatus(Enum):
    NoAnnotation = 1
    Annotated = 2
    MarkedDrop = 3
    PerformingAnnotation = 4

class EDatasetType(Enum):
    YamlYOLO = 1
    TxtYOLO = 2

class EImagesType(Enum):
    Train = 1
    Valid = 2
    Test = 3

class FAnnotationClasses:
    class FClassData:
        def __init__(self, name: str, color: QColor):
            self.Name = name
            self.Color = color

    def __init__(self):
        self.class_dict: dict[int, FAnnotationClasses.FClassData] = dict()

    def __str__(self):
        str_dict = ""
        for key, value in self.class_dict.items():
            str_dict += f"{key}: {value.Name}, цвет: {value.Color}\n"
        return str_dict

    def add_classes_from_strings(self, str_list: list[str]):
        for index in range(len(str_list)):
            error = self.add_class(index, str_list[index], FAnnotationClasses.get_save_color(index))
            if error: return error
        return

    def add_class_by_name(self, name: str):
        index = len(self)
        return self.add_class(index, name, FAnnotationClasses.get_save_color(index))

    def add_class(self, class_id: int, name: str, color: QColor):
        if class_id in self.class_dict:
            return f"Ошибка! Класс под ID {class_id} уже существует!"
        self.class_dict[class_id] = FAnnotationClasses.FClassData(name, color)
        return

    def get_color(self, class_id: int):
        if class_id not in self.class_dict:
            return None
        return self.class_dict[class_id].Color

    def get_name(self, class_id: int):
        if class_id not in self.class_dict:
            return None
        return self.class_dict[class_id].Name

    def get_class(self, class_id: int):
        return self.class_dict.get(class_id)

    def get_all_classes(self):
        return self.class_dict.values()

    def get_all_ids(self):
        return self.class_dict.keys()

    def get_items(self):
        return self.class_dict.items()

    def __len__(self):
        return len(self.class_dict)

    @staticmethod
    def get_save_color(class_id: int):
        """
        if id_class >= len(GColorList):
            #return QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

            step = 255
            r, g, b = 255, 255, 255

            for i in range((id_class - len(GColorList)) % 3 + 1):
                if i % 3 == 0 and i != 0:
                    step //= 2
                if i % 3 == 0:
                    r = step if id_class % 2 == 0 else 255 - step
                elif i % 3 == 1:
                    g = step if id_class % 2 == 0 else 255 - step
                else:
                    b = step if id_class % 2 == 0 else 255 - step

            return QColor(r, g, b)
        else:
            return GColorList[id_class]
        """
        random.seed(class_id)  # Фиксируем случайность для одинаковых результатов

        hue = random.randint(0, 359)  # Оттенок на цветовом круге
        saturation = random.randint(150, 255)  # Разброс насыщенности
        value = random.randint(180, 255)  # Разброс яркости

        return QColor.fromHsv(hue, saturation, value)

class FAnnotationData:
    def __init__(self, class_id: int, class_name: str, color: QColor, res_w = 1920, res_h = 1400):
        self.ClassID = class_id
        self.class_name = class_name
        self.color = color
        self.Resolution_w = res_w
        self.Resolution_h = res_h

    def __str__(self):
        return f"Объект аннотации не инициализирован!"

    def get_data(self):
        pass

    def get_rect_to_draw(self):
        return QRect()

    def get_polygon_to_draw(self):
        pass

    def get_color(self):
        return self.color

    def get_class_name(self):
        return self.class_name

    def get_id(self):
        return self.ClassID

    def get_resolution(self):
        return self.Resolution_w, self.Resolution_h

class FDetectAnnotationData(FAnnotationData):
    def __init__(self, x, y, width, height, class_id: int, class_name: str, color: QColor, res_w = 1920, res_h = 1400):
        super().__init__(class_id, class_name, color, res_w, res_h)
        self.X = x
        self.Y = y
        self.Width = width
        self.Height = height

    def __str__(self):
        if self.X < 0: self.X = 0
        if self.Y < 0: self.Y = 0
        if self.X + self.Width > self.Resolution_w: self.Width = self.Resolution_w - self.X
        if self.Y + self.Height > self.Resolution_h: self.Height = self.Resolution_h - self.Y
        return (f"{self.ClassID} "
                f"{(self.X + self.Width / 2) / float(self.Resolution_w)} "
                f"{(self.Y + self.Height / 2) / float(self.Resolution_h)} "
                f"{self.Width / float(self.Resolution_w)} "
                f"{self.Height / float(self.Resolution_h)}")

    def get_data(self):
        return self.X, self.Y, self.Width, self.Height

    def get_rect_to_draw(self):
        top_left = QPoint(int(self.X), int(self.Y))
        bottom_right = QPoint(int(self.X + self.Width), int(self.Y + self.Height))
        return QRect(top_left, bottom_right)

class FAnnotationItem:
    def __init__(self, ann_list: list[FAnnotationData], image_path: str):
        self.annotation_list = ann_list
        self.image_path = image_path

    def get_item_data(self):
        return self.annotation_list, self.image_path

    def get_image_path(self):
        return self.image_path


class FDatasetInfo:
    config_name = "config.cfg"
    section = "Save"
    counter_option = "counter"

    def __init__(self, path:str, dataset_type: EDatasetType = None):
        self.dataset_type: Optional[EDatasetType] = None

        self.counter: int = 1
        self.paths: dict[str, str] = dict()

        self.nc: int = 0
        self.class_names: list[str] = list()

        # Используется при загрузке готового датасета
        if os.path.isfile(path):
            self.datafile_path = path
            self.path_general: str = os.path.dirname(self.datafile_path)
            self.path_config: str = os.path.join(self.path_general, self.config_name).replace("\\", "/")
            if path.endswith(".yaml"):
                self.dataset_type = EDatasetType.YamlYOLO
            elif path.endswith(".txt"):
                self.dataset_type = EDatasetType.TxtYOLO
            else:
                print(f"Невозможно прочитать файл {path}")
                return
        # Создание нового датасета
        elif os.path.isdir(path):
            self.dataset_type = dataset_type
            if self.dataset_type is None:
                print("Некорректные данные при создании датасета! Был указан тип None!")
                return
            else:
                self.path_general: str = path
                self.path_config: str = os.path.join(self.path_general, self.config_name).replace("\\", "/")
            if self.dataset_type.value == EDatasetType.YamlYOLO.value:
                self.datafile_path = os.path.join(path, "data.yaml").replace("\\", "/")
            elif self.dataset_type.value == EDatasetType.TxtYOLO.value:
                self.datafile_path = os.path.join(path, "classes.txt").replace("\\", "/")
        else:
            print(f"Невозможно прочитать файл {path}")

        self.set_dataset_info()

    def set_dataset_info(self):
        if os.path.exists(self.datafile_path) is False:
            print(f"Не существует файла {self.datafile_path}")
            if self.dataset_type.value == EDatasetType.YamlYOLO.value:
                self.paths = {
                    "train_images": os.path.join(self.path_general, "train/images").replace("\\", "/"),
                    "train_labels": os.path.join(self.path_general, "train/labels").replace("\\", "/"),
                    "valid_images": os.path.join(self.path_general, "valid/images").replace("\\", "/"),
                    "valid_labels": os.path.join(self.path_general, "valid/labels").replace("\\","/"),
                    "test_images": os.path.join(self.path_general, "test/images").replace("\\", "/"),
                    "test_labels": os.path.join(self.path_general, "test/labels").replace("\\","/"),
                }
            elif self.dataset_type.value == EDatasetType.TxtYOLO.value:
                self.paths = {
                    "images": os.path.join(self.path_general, "images").replace("\\", "/"),
                    "labels": os.path.join(self.path_general, "labels").replace("\\", "/"),
                }
        else:
            if self.dataset_type.value == EDatasetType.YamlYOLO.value:
                if self.check_yaml_yolo_file() == -2:
                    print(f"Не удалось открыть файл {self.datafile_path}")
                    return False
            elif self.dataset_type.value == EDatasetType.TxtYOLO.value:
                if self.check_txt_yolo_file() == -1:
                    return False

        if os.path.exists(self.path_config):
            self.check_config_file()
        else:
            print(f"Отсутствует файл {self.path_config}")

        print(f"Данные о датасете загружены!\n"
              f"Пути к файлам: {self.paths}\n"
              f"nc: {self.nc}\n"
              f"names: {self.class_names}\n"
              f"counter: {self.counter}")

    def check_yaml_yolo_file(self):
        with open(self.datafile_path, "r") as data_yaml:
            try:
                data = yaml.safe_load(data_yaml)

                self.paths = {
                    "train_images": os.path.join(self.path_general, data.get("train", "../train/images").lstrip("./")).replace("\\", "/"),
                    "train_labels": os.path.join(self.path_general, data.get("train", "../train/images").lstrip("./").removesuffix("/images") + "/labels").replace("\\", "/"),
                    "valid_images": os.path.join(self.path_general, data.get("val", "../valid/images").lstrip("./")).replace("\\", "/"),
                    "valid_labels": os.path.join(self.path_general, data.get("val", "../valid/images").lstrip("./").removesuffix("/images") + "/labels").replace("\\", "/"),
                    "test_images": os.path.join(self.path_general, data.get("test", "../test/images").lstrip("./")).replace("\\", "/"),
                    "test_labels": os.path.join(self.path_general, data.get("test", "../test/images").lstrip("./").removesuffix("/images") + "/labels").replace("\\", "/"),
                }
                self.nc = data.get("nc", 0)
                self.class_names = data.get("names", [])

            except yaml.YAMLError as e:
                print(f"Ошибка Yaml: {str(e)}")
                return -2

    def check_txt_yolo_file(self):
        with open(self.datafile_path, "r") as data_txt:
            try:
                self.class_names = [line.strip() for line in data_txt]
                self.nc = len(self.class_names)
                self.paths = {
                    "images": os.path.join(self.path_general, "images").replace("\\", "/"),
                    "labels": os.path.join(self.path_general, "labels").replace("\\", "/"),
                }
            except Exception as e:
                print(f"Ошибка : {str(e)}")
                return -1

    def create_txt_yolo_file(self, class_names: list[str] = None):
        if class_names is None:
            write_names = self.class_names
        else:
            write_names = class_names
        try:
            with open(self.datafile_path, "w") as data_txt:
                for line in write_names:
                    data_txt.write(line + '\n')
        except Exception as e:
            print (f"Ошибка: {str(e)}")

    def check_config_file(self):
        try:
            config = configparser.ConfigParser()
            config.read(self.path_config)
        except Exception as e:
            print(f"Ошибка: {e}")
            return -2
        try:
            self.counter = config[self.section].getint(self.counter_option, 1)
            return 1
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            self.counter = 1
            print(f"Ошибка: {e}")
            return -1

    def create_config_file(self):
        config = configparser.ConfigParser()

        config.add_section(self.section)
        config.set(self.section, self.counter_option, str(self.counter))

        with open(self.path_config, 'w+') as config_file:
            config.write(config_file)

    def create_dataset_carcass(self):
        for key, value in self.paths.items():
            os.makedirs(value, exist_ok=True)

    def get_type_index(self):
        return int(self.dataset_type.value) - 1


class UMessageBox:
    @staticmethod
    def show_error(message: str, title: str = "Ошибка", status: int = QMessageBox.Critical):
        msg_box = QMessageBox()
        msg_box.setIcon(status)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()