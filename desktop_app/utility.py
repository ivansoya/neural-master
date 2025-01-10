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
