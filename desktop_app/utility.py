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
    def __init__(self, ann_list: list[FAnnotationData], image_path: str, dataset_name: str | None):
        self.annotation_list = ann_list
        self.image_path = image_path
        self.dataset: Optional[str] = dataset_name

    def get_item_data(self):
        return self.annotation_list

    def get_image_path(self):
        return self.image_path

    def get_dataset_name(self):
        return self.dataset

class UMessageBox:
    @staticmethod
    def show_error(message: str, title: str = "Ошибка", status: int = QMessageBox.Critical):
        msg_box = QMessageBox()
        msg_box.setIcon(status)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()