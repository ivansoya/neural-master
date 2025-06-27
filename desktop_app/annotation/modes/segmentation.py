from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMouseEvent, QKeyEvent

from annotation.annotation_item import UAnnotationItem
from annotation.annotation_polygon import UAnnotationPolygon
from annotation.modes.abstract import UBaseAnnotationMode, EWorkMode
from commander import UAnnotationSignalHolder
from supporting.functions import get_clamped_pos
from utility import FAnnotationData

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView


class UMaskAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        super().__init__()
        self.scene = scene
        self.commander = commander

        self.current_mask: Optional[UAnnotationPolygon] = None

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
            if self.current_mask:
                self.current_mask.delete_item()
        else:
            if self.current_mask and not self.current_mask.is_closed():
                self.current_mask.delete_item()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def refresh(self):
        self.current_mask = None

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def on_move_mouse(self, event: QMouseEvent):
        image = self.scene.get_image()
        if not self.current_mask or not image:
            return

        self.current_mask.move(get_clamped_pos(self.scene, event.pos(), image))
        self.scene.scene().update()

    def on_release_mouse(self, event: QMouseEvent):
        image, class_data = self.scene.get_image(), self.scene.get_current_class()
        if not image or not class_data:
            return

        if event.button() == Qt.LeftButton:
            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)
            if not self.current_mask:
                self.scene.scene().clearSelection()
                self.current_mask = self.scene.add_annotation_mask(
                    [cursor_pos_image],
                    class_data
                )
                self.current_mask.disable_selection()
            else:
                if self.current_mask.fix_point():
                    self.scene.emit_commander_to_add(self.current_mask.get_annotation_data())

                    self.current_mask.setSelected(False)
                    self.current_mask.change_points_visibility(False)
                    self.current_mask = None

    def on_press_mouse(self, event: QMouseEvent):
        pass

    def on_key_release(self, key: int):
        return

    def on_key_hold(self, key: int):
        return

    def on_key_press(self, key: int):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, mask: UAnnotationItem):
        if self.current_mask is mask:
            self.current_mask = None

    def on_wheel_mouse(self, scale: float):
        return
