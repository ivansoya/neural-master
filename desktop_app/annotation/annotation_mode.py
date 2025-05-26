from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QGraphicsView

from annotation.annotation_box import UAnnotationBox
from annotation.annotation_mask import UAnnotationMask
from commander import UGlobalSignalHolder, UAnnotationSignalHolder

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView


class EWorkMode(Enum):
    DragMode = 1
    ForceDragMode = 2
    GettingResultsMode = 3
    BoxAnnotationMode = 4
    MaskAnnotationMode = 5

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

class UDragAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.DragMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode):
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        return

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        return

    def on_move_mouse(self, event):
        return

    def on_press_mouse(self, event):
        return

    def on_release_mouse(self, event):
        selected = self.scene.get_selected_annotation()
        if selected is None:
            pass
        else:
            index = self.scene.annotation_items.index(selected)
            self.commander.updated_annotation.emit(
                self.scene.get_current_thumb_index(),
                index,
                None,
                selected.get_annotation_data()
            )
        return


class UForceDragAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UGlobalSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.ForceDragMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode):
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.scene.setDragMode(QGraphicsView.ScrollHandDrag)
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()
        self.scene.setDragMode(QGraphicsView.NoDrag)
        return

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        return

    def on_move_mouse(self, event):
        return

    def on_press_mouse(self, event):
        return

    def on_release_mouse(self, event):
        return


class UBoxAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.current_rect: Optional[UAnnotationBox] = None
        self.start_point: Optional[QPointF] = None

        self.mode = EWorkMode.BoxAnnotationMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode):
        if prev_mode is self.mode:
            return
        self.scene.scene().clearSelection()
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        if self.mode is change_mode or change_mode is EWorkMode.ForceDragMode:
            return
        elif change_mode is EWorkMode.GettingResultsMode:
            self._delete_current_rect()
        else:
            self._clean_rect()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        self._delete_current_rect()
        return

    def on_press_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class()):
            return

        # Если в режиме сохранен какой-то прямоугольник, его необходимо оставить на сцене
        if self.current_rect and self.start_point:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.DragMode.value)
        # Создание нового прямоугольника
        elif not (self.current_rect and self.start_point):
            cursor_pos = self.scene.mapToScene(event.pos())
            self.start_point = self.scene.get_image().mapFromScene(cursor_pos)
            self.current_rect = self.scene.add_annotation_box(
                self.start_point.x(),
                self.start_point.y(),
                1,
                1,
                self.scene.get_current_class(),
            )

    def on_move_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class() and self.current_rect and self.start_point):
            return

        current_cursor_pos = self.scene.get_image().mapFromScene(self.scene.mapToScene(event.pos()))
        rect = QRectF(self.start_point, current_cursor_pos).normalized()
        self.current_rect.setRect(rect)

    def on_release_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class() and self.current_rect and self.start_point):
            return

        if self.current_rect.get_square() < 25:
            self._delete_current_rect()
            return
        if self.commander:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self.current_rect.setSelected(True)
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.DragMode.value)

    def _clean_rect(self):
        self.current_rect = None
        self.start_point = None

    def _delete_current_rect(self):
        if self.current_rect and self.current_rect in self.scene.get_annotations():
            self.scene.delete_annotation_item(self.current_rect)
        self._clean_rect()


class UMaskAnnotaionMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.current_mask: Optional[UAnnotationMask] = None

        self.mode = EWorkMode.MaskAnnotationMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode: EWorkMode):
        self.scene.scene().clearSelection()
        if prev_mode is self.mode:
            return
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.previous_mode = prev_mode

    def end_mode(self, change_mode: EWorkMode):
        if change_mode in [EWorkMode.ForceDragMode, EWorkMode.MaskAnnotationMode]:
            return
        elif change_mode is EWorkMode.GettingResultsMode:
            self._delete_mask()
        else:
            self._clean_mask()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def _delete_mask(self):
        if self.current_mask and self.current_mask in self.scene.get_annotations():
            self.current_mask.delete_mask()
            self.scene.delete_annotation_item(self.current_mask)
        self.current_mask = None

    def _clean_mask(self):
        self.current_mask = None

