from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from PyQt5.QtGui import QMouseEvent, QKeyEvent

from annotation.annotation_item import UAnnotationItem
from utility import FAnnotationData

if TYPE_CHECKING:
    pass


class EWorkMode(Enum):
    Viewer = 1
    ForceDragMode = 2
    GettingResultsMode = 3
    BoxAnnotationMode = 4
    MaskAnnotationMode = 5
    SAM2 = 6

class UBaseAnnotationMode(ABC):
    @abstractmethod
    def start_mode(self, prev_mode: EWorkMode):
        pass

    @abstractmethod
    def end_mode(self, mode: EWorkMode):
        pass

    @abstractmethod
    def get_previous_mode(self) -> EWorkMode | None:
        pass

    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def on_press_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_move_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_release_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_key_press(self, event: QKeyEvent):
        pass

    @abstractmethod
    def on_key_release(self, event: QKeyEvent):
        pass

    @abstractmethod
    def on_select_item(self, item: UAnnotationItem):
        pass

    @abstractmethod
    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        pass

    @abstractmethod
    def on_delete_item(self, item: UAnnotationItem):
        pass

    @abstractmethod
    def on_wheel_mouse(self, scale: float):
        pass

