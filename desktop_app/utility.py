import os.path
from abc import abstractmethod
from typing import Optional

import yaml
import configparser
from enum import Enum

from PyQt5.QtCore import Qt, QPointF, QPoint, QRect, QRectF
from PyQt5.QtGui import QColor, QPolygonF

import random

from PyQt5.QtWidgets import QMessageBox
from sympy import andre

from supporting.functions import clamp, segmentation_area

GColorList = [
    QColor(255, 0, 0),
    QColor(0, 255, 0),
    QColor(0, 0, 255),
    QColor(255, 255, 0),
    QColor(255, 0, 255),
    QColor(0, 255, 255),
]

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

class EAnnotationType(Enum):
    BoundingBox = 1
    Segmentation = 2
    Mask = 3
    NoType = 4

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
    def __init__(
            self,
            annotation_id: int,
            bbox: list[float],
            segmentation: list,
            class_id: int,
            class_name: str,
            color: QColor,
            res_w = 1920,
            res_h = 1400
    ):
        if len(segmentation) >= 2:
            self.type = EAnnotationType.Mask
        elif len(segmentation) == 1:
            self.type = EAnnotationType.Segmentation
        elif len(bbox) == 4:
            self.type = EAnnotationType.BoundingBox
        else:
            self.type = EAnnotationType.NoType

        self.annotation_id = annotation_id
        self.bbox = bbox
        self.segmentation = segmentation

        self.class_id = class_id
        self.class_name = class_name
        self.color = color

        self.w_resolution = res_w
        self.h_resolution = res_h

    def clamp_cords(self):
        return

    def get_bbox(self) -> list[float]:
        return self.bbox

    def get_segmentation(self) -> list:
        return self.segmentation

    def get_area(self) -> float:
        if self.type is EAnnotationType.BoundingBox and len(self.bbox) == 4:
            return self.bbox[2] * self.bbox[3]
        else:
            return segmentation_area(self.segmentation)

    def _copy_init_args(self):
        return self.annotation_id, self.bbox, self.segmentation, self.class_id, self.class_name, QColor(self.color), self.w_resolution, self.h_resolution

    def copy(self):
        return FAnnotationData(*self._copy_init_args())

    def __str__(self):
        return f"Объект аннотации не инициализирован!"

    def serialize(self, class_id: int) -> str:
        return f"Объект аннотации не инициализирован!"

    def update_data(self, data: 'FAnnotationData'):
        self.annotation_id = data.annotation_id
        self.bbox = data.bbox
        self.segmentation = data.segmentation

        self.class_id = data.class_id
        self.class_name = data.class_name
        self.color = data.color

        self.w_resolution = data.w_resolution
        self.h_resolution = data.h_resolution

    def get_color(self):
        return self.color

    def get_class_name(self):
        return self.class_name

    def get_annotation_id(self):
        return self.annotation_id

    def get_class_id(self):
        return self.class_id

    def set_class_id(self, class_id: int):
        self.class_id = class_id

    def get_resolution(self):
        return self.w_resolution, self.h_resolution

    def get_annotation_type(self) -> EAnnotationType:
        return self.type

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented

        return (
                self.annotation_id == other.annotation_id and
                self.w_resolution == other.w_resolution and
                self.h_resolution == other.h_resolution
        )

    def __ne__(self, other):
        return not self == other

class FAnnotationItem:
    def __init__(self, ann_list: list[FAnnotationData], image_path: str, image_id: int, dataset_name: str | None):
        self.annotation_list = ann_list
        self.image_path = image_path
        self.dataset: Optional[str] = dataset_name
        self.image_id = image_id

    def copy(self):
        return self.__class__(
            [annotation.copy() for annotation in self.annotation_list],
            str(self.image_path),
            self.image_id,
            str(self.dataset)
        )

    def update_annotation_data(self, annotation_data: list[FAnnotationData]):
        self.annotation_list.clear()
        self.annotation_list = list(annotation_data)

    def get_annotation_data(self):
        return self.annotation_list

    def get_image_path(self):
        return self.image_path.strip().replace('\\', '/')

    def get_dataset_name(self):
        return self.dataset

    def get_image_id(self):
        return self.image_id

    def set_image_id(self, image_id: int):
        self.image_id = image_id

    def set_dataset_name(self, dataset_name: str):
        self.dataset = dataset_name

    def set_image_path(self, image_path: str):
        self.image_path = image_path

    def __eq__(self, other):
        if not isinstance(other, FAnnotationItem):
            return self is other
        else:
            return (self.get_image_id() == other.get_image_id() and
                    self.image_path == other.get_image_path() and
                    self.dataset == other.get_dataset_name())

    def __ne__(self, other):
        return not self == other


class UMessageBox:
    @staticmethod
    def show_error(message: str):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Ошибка")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    @staticmethod
    def show_warning(message: str):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Предупреждение!")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    @staticmethod
    def show_ok(message: str):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Успешно")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    @staticmethod
    def ask_confirmation(message: str, title: str = "Подтверждение") -> bool:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        result = msg_box.exec_()
        return result == QMessageBox.Yes
