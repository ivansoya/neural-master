import os.path
import yaml
import configparser
from enum import Enum
from PyQt5.QtGui import QColor

import random


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

class EAnnotationStatus(Enum):
    NoAnnotation = 1
    Annotated = 2
    MarkedDrop = 3

class FDatasetInfo:
    config_name = "config.cfg"
    section = "Save"
    counter_option = "counter"

    def __init__(self, path:str):
        if os.path.isfile(path):
            if path.endswith(".yaml"):
                self.path_yaml = path
                self.path_general: str = os.path.dirname(self.path_yaml)
                self.path_config: str = os.path.join(self.path_general, self.config_name).replace("\\", "/")
                self.is_exists = True
            else:
                print(f"Невозможно прочитать файл {path}")
                return
        elif os.path.isdir(path):
            self.path_yaml = os.path.join(path, "data.yaml").replace("\\", "/")
            self.path_general: str = path
            self.path_config: str = os.path.join(self.path_general, self.config_name).replace("\\", "/")
        else:
            print(f"Невозможно прочитать файл {path}")

        self.counter: int = 1
        self.paths: dict[str, str] = dict()

        self.nc: int = 0
        self.class_names: list[str] = list()

        self.set_dataset_info()

    def set_dataset_info(self):
        if os.path.exists(self.path_yaml) is False:
            print(f"Не существует файла {self.path_yaml}")
            self.paths = {
                "train_images": os.path.join(self.path_general, "train/images").replace("\\", "/"),
                "train_labels": os.path.join(self.path_general, "train/labels").replace("\\", "/"),
                "valid_images": os.path.join(self.path_general, "valid/images").replace("\\", "/"),
                "valid_labels": os.path.join(self.path_general, "valid/labels").replace("\\","/"),
                "test_images": os.path.join(self.path_general, "test/images").replace("\\", "/"),
                "test_labels": os.path.join(self.path_general, "test/labels").replace("\\","/"),
            }
        elif self.check_yaml_file() == -2:
            print(f"Не удалось открыть файл {self.path_yaml}")
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

    def check_yaml_file(self):
        with open(self.path_yaml, "r") as data_yaml:
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

class FClassData:
    def __init__(self, id_class, name, color: QColor):
        self.Cid = id_class
        self.Name = name
        self.Color = color

    def __str__(self):
        return f"{self.Cid}: {self.Name}"

    @staticmethod
    def get_save_color(id_class: int):
        if id_class >= len(GColorList):
            return QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        else:
            return GColorList[id_class]

class FAnnotationData:
    def __init__(self, x, y, width, height, class_id, res_w = 1920, res_h = 1400):
        self.X = x
        self.Y = y
        self.Width = width
        self.Height = height
        self.ClassID = class_id
        self.Resolution_w = res_w
        self.Resolution_h = res_h

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
