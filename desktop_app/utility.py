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
