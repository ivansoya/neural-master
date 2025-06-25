from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QKeyEvent

from annotation.annotation_box import UAnnotationBox
from annotation.annotation_item import UAnnotationItem
from annotation.modes.abstract import UBaseAnnotationMode, EWorkMode
from commander import UAnnotationSignalHolder
from utility import FAnnotationData

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView

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
        self._delete_current()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        self._clean_rect()
        return

    def on_press_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class()):
            return

        # Если в режиме сохранен какой-то прямоугольник, его необходимо оставить на сцене
        if self.current_rect and self.start_point:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.Viewer.value)
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
            self._delete_current()
            return
        if self.commander:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self.current_rect.setSelected(True)
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.Viewer.value)

    def on_key_release(self, key: int):
        return

    def on_key_hold(self, key: int):
        pass

    def on_key_press(self, key: int):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        if self.current_rect is item:
            self._clean_rect()
        return

    def on_wheel_mouse(self, scale: float):
        return

    def _delete_current(self):
        if self.current_rect:
            self.current_rect.delete_item()
            if self.current_rect in self.scene.get_annotations() and self.current_rect.scene():
                self.scene.scene().removeItem(self.current_rect)
                self.scene.get_annotations().remove(self.current_rect)
        self._clean_rect()

    def _clean_rect(self):
        self.current_rect = None
        self.start_point = None
