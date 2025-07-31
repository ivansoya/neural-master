from dataclasses import dataclass
from enum import StrEnum

from PyQt5.QtGui import QColor

IMAGES_DIR = "images"

class ECocoFileNames(StrEnum):
    TRAIN_DIR = "images/train"
    VAL_DIR = "images/val"
    ANNOTATION_DIR = "annotations"
    TRAIN_JSON = "instances_train.json"
    VAL_JSON = "instances_val.json"

class EDefaultTrainName(StrEnum):
    TRAIN_IMAGES = "images/train"
    TRAIN_LABELS = "labels/train"
    VAL_IMAGES = "images/val"
    VAL_LABELS = "labels/val"

    IMAGES = "images"
    LABELS = "labels"
    CLASSES = "classes.txt"

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
