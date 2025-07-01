from dataclasses import dataclass

from PyQt5.QtGui import QColor

@dataclass
class UProjectInfo:
    name: str
    description: str
    author: str
    year: int
    licenses: list


@dataclass
class UAnnotationClass:
    name: str
    color: QColor
    super_category: str
