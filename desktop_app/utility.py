import os.path
from typing import Optional

import yaml
import configparser
from enum import Enum

from PyQt5.QtCore import Qt, QPointF, QPoint, QRect, QRectF
from PyQt5.QtGui import QColor, QPolygonF

import random

from PyQt5.QtWidgets import QMessageBox

from supporting.functions import clamp

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
    NoType = 3

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
    def __init__(self, object_id: int, class_id: int, class_name: str, color: QColor, res_w = 1920, res_h = 1400):
        self.object_id = object_id
        self.class_id = class_id
        self.class_name = class_name
        self.color = color
        self.w_resolution = res_w
        self.h_resolution = res_h

    def _copy_init_args(self):
        return self.object_id, self.class_id, self.class_name, QColor(self.color), self.w_resolution, self.h_resolution

    def copy(self):
        return FAnnotationData(*self._copy_init_args())

    def __str__(self):
        return f"Объект аннотации не инициализирован!"

    def serialize(self, class_id: int) -> str:
        return f"Объект аннотации не инициализирован!"

    def update_data(self, data):
        pass

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

    def get_object_id(self):
        return self.object_id

    def get_id(self):
        return self.class_id

    def get_resolution(self):
        return self.w_resolution, self.h_resolution

    def get_annotation_type(self):
        return EAnnotationType.NoType

    def __eq__(self, other):
        if not isinstance(other, FAnnotationData):
            return self is other
        return (
                self.object_id == other.object_id and
                self.class_id == other.class_id and
                self.class_name == other.class_name and
                self.color == other.color and
                self.w_resolution == other.w_resolution and
                self.h_resolution == other.h_resolution
        )

    def __ne__(self, other):
        return not self == other

class FDetectAnnotationData(FAnnotationData):
    def __init__(self, x, y, width, height, object_id: int, class_id: int, class_name: str, color: QColor, res_w = 1920, res_h = 1400):
        super().__init__(object_id, class_id, class_name, color, res_w, res_h)
        self.X = x
        self.Y = y
        self.Width = width
        self.Height = height

    def _clamp_bbox(self):
        self.X = max(0, self.X)
        self.Y = max(0, self.Y)
        self.Width = min(self.Width, self.w_resolution - self.X)
        self.Height = min(self.Height, self.h_resolution - self.Y)

    def serialize(self, class_id: int = None) -> str:
        self._clamp_bbox()
        serialized_class_id = self.class_id if class_id is None else class_id

        x_center = (self.X + self.Width / 2) / self.w_resolution
        y_center = (self.Y + self.Height / 2) / self.h_resolution
        width = self.Width / self.w_resolution
        height = self.Height / self.h_resolution

        return f"{serialized_class_id} {x_center} {y_center} {width} {height}"

    def __str__(self):
        return self.serialize()

    def get_annotation_type(self):
        return EAnnotationType.BoundingBox

    def copy(self):
        return FDetectAnnotationData(
            self.X,
            self.Y,
            self.Width,
            self.Height,
            *self._copy_init_args()
        )

    def get_data(self):
        return (self.object_id, self.class_id, self.class_name, self.color,
                (self.X, self.Y, self.Width, self.Height))

    def update_data(self, data: tuple[int, int, str, QColor, tuple[int, int, int, int]]):
        self.object_id, self.class_id, self.class_name, color, (self.X, self.Y, self.Width, self.Height) = data
        self.color = QColor(color)

    def get_rect_to_draw(self):
        top_left = QPoint(int(self.X), int(self.Y))
        bottom_right = QPoint(int(self.X + self.Width), int(self.Y + self.Height))
        return QRect(top_left, bottom_right)

    def __eq__(self, other):
        if not isinstance(other, FDetectAnnotationData):
            return self is other
        return (
                super().__eq__(other) and
                self.X == other.X and
                self.Y == other.Y and
                self.Width == other.Width and
                self.Height == other.Height
        )

    def __ne__(self, other):
        return not self == other


class FPolygonAnnotationData(FAnnotationData):
    def __init__(self, points_list: list[tuple[float, float]], annotation_id: int, class_id: int, class_name: str, color: QColor, res_w = 1920, res_h = 1400):
        super().__init__(annotation_id, class_id, class_name, color, res_w, res_h)
        self.points_list = points_list

    def serialize(self, class_id: int = None) -> str:
        points_str = " ".join(
            f"{clamp(x, 0, self.w_resolution) / self.w_resolution} {clamp(y, 0, self.h_resolution) / self.h_resolution}"
            for x, y in self.points_list
        )

        serialized_class_id = self.class_id if class_id is None else class_id

        return f"{serialized_class_id} {points_str}"

    def __str__(self):
        return self.serialize()

    def copy(self):
        return FPolygonAnnotationData(
            self.points_list[:],
            *self._copy_init_args()
        )

    def get_annotation_type(self):
        return EAnnotationType.Segmentation

    def get_data(self):
        return self.object_id, self.class_id, self.class_name, self.color, self.points_list

    def get_points_list(self):
        return self.points_list

    def get_polygon_to_draw(self):
        return QPolygonF([QPointF(x, y) for x, y in self.points_list])

    def update_data(self, data: tuple[int, int, str, QColor, list[tuple[float, float]]]):
        self.object_id, self.class_id, self.class_name, color, list_points = data
        self.color = QColor(color)
        self.points_list = list_points[:]

    def get_rect_to_draw(self):
        min_x, min_y, max_x, max_y = self.w_resolution, self.h_resolution, 0, 0
        for x, y in self.points_list:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
        return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))

    def __eq__(self, other):
        if not isinstance(other, FPolygonAnnotationData):
            return self is other
        return (
                super().__eq__(other) and
                self.points_list == other.points_list
        )

    def __ne__(self, other):
        return not self == other

class FAnnotationItem:
    def __init__(self, ann_list: list[FAnnotationData], image_path: str, dataset_name: str | None):
        self.annotation_list = ann_list
        self.image_path = image_path
        self.dataset: Optional[str] = dataset_name

    def copy(self):
        return self.__class__(
            [annotation.copy() for annotation in self.annotation_list],
            str(self.image_path),
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

    def set_dataset_name(self, dataset_name: str):
        self.dataset = dataset_name

    def __eq__(self, other):
        if not isinstance(other, FAnnotationItem):
            return self is other
        else:
            return self.image_path == other.get_image_path() and self.dataset == other.get_dataset_name()


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