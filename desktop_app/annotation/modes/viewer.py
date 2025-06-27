from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QMenu, QGraphicsView

from annotation.annotation_box import UAnnotationBox
from annotation.annotation_item import UAnnotationItem
from annotation.annotation_polygon import UAnnotationPolygon
from annotation.modes.abstract import UBaseAnnotationMode, EWorkMode
from commander import UAnnotationSignalHolder, UGlobalSignalHolder
from supporting.functions import get_clamped_pos
from utility import FAnnotationData

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView

class UViewerMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.Viewer
        self.previous_mode: Optional[EWorkMode] = None

        self.mask_adding_point_mode = False
        self.last_mask: Optional[UAnnotationPolygon] = None

    def start_mode(self, prev_mode):
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        self.mask_adding_point_mode = False
        self.last_mask = None
        return

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        self.mask_adding_point_mode = False
        self.last_mask = None
        return

    def on_move_mouse(self, event):
        return

    def on_press_mouse(self, event):
        image = self.scene.get_image()
        if not image:
            return

        if event.button() == Qt.LeftButton and self.mask_adding_point_mode:
            if self.last_mask is None:
                return
            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)
            self.last_mask.add_point(cursor_pos_image)
            self.scene.scene().update()
            return 1

        if event.button() == Qt.RightButton:
            boxes_to_interact: list[UAnnotationBox] = []
            selected = self.scene.scene().selectedItems()
            for item in selected:
                if not isinstance(item, UAnnotationBox):
                    continue
                boxes_to_interact.append(item)

            if len(boxes_to_interact) <= 0:
                return

            menu_actions = [
                ("Преобразовать боксы в маски", lambda: [self.scene.remake_box_to_mask(box) for box in boxes_to_interact]),
            ]

            self._create_contex_menu(event, menu_actions)

    def on_release_mouse(self, event):
        return

    def on_key_press(self, key: int):
        if key == Qt.Key_Alt:
            selected = [item for item in self.scene.scene().selectedItems() if isinstance(item, UAnnotationPolygon)]
            if len(selected) > 0:
                self.last_mask = max(selected, key=lambda item: item.zValue())
            else:
                self.last_mask = None

            if self.last_mask:
                self.mask_adding_point_mode = True
                QApplication.setOverrideCursor(Qt.CrossCursor)
        if key == Qt.Key_Delete:
            selected = [ item for item in self.scene.scene().selectedItems() if isinstance(item, UAnnotationItem)]
            for item in selected:
                self.scene.handle_on_delete_annotation_item(item)

    def on_key_hold(self, key: int):
        return

    def on_key_release(self, key: int):
        if key == Qt.Key_Alt and self.mask_adding_point_mode:
            QApplication.restoreOverrideCursor()
            self.mask_adding_point_mode = False
            self.last_mask = None

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        self.last_mask = None
        return

    def on_wheel_mouse(self, scale: float):
        return

    def _create_contex_menu(self, event, menu_items):
        menu = QMenu(self.scene)

        for text, func in menu_items:
            action = menu.addAction(text)
            action.triggered.connect(func)

        menu.exec_(event.globalPos())


class UForceDragAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UGlobalSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.ForceDragMode
        self.previous_mode: Optional[EWorkMode] = None

        self.mask_adding_point_mode: bool = False

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

    def on_key_release(self, key: int):
        return

    def on_key_press(self, key: int):
        return

    def on_key_hold(self, key: int):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        return

    def on_wheel_mouse(self, scale: float):
        return
