from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import Qt, QPointF
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

        self.polygons: list[UAnnotationPolygon] = list()
        self.current_polygon: Optional[UAnnotationPolygon] = None

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
            return True
        elif not self.is_work_done():
            return False
        else:
            self._clear_scene()
            for annotation in self.scene.get_annotations():
                annotation.enable_selection()
            return True

    def refresh(self):
        if self.is_work_done():
            self.polygons.clear()
            self.current_polygon = None
            return True
        else:
            return False

    def is_work_done(self) -> bool:
        return True if len(self.polygons) == 0 else False

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def on_move_mouse(self, event: QMouseEvent):
        image = self.scene.get_image()
        if not self.current_polygon or not image:
            return

        self.current_polygon.move(get_clamped_pos(self.scene, event.pos(), image))
        self.scene.scene().update()

    def on_release_mouse(self, event: QMouseEvent):
        image, class_data = self.scene.get_image(), self.scene.get_current_class()
        if not image or not class_data:
            return

        if event.button() == Qt.LeftButton:
            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)
            if not self.current_polygon:
                self.scene.scene().clearSelection()
                self.current_polygon = self._add_polygon_to_scene(cursor_pos_image, class_data)
            else:
                if self.current_polygon.fix_point():
                    self.current_polygon.setSelected(False)
                    self.current_polygon.change_points_visibility(False)
                    self.current_polygon = None

    def on_press_mouse(self, event: QMouseEvent):
        pass

    def on_key_release(self, key: int):
        return

    def on_key_hold(self, key: int):
        return

    def on_key_press(self, key: int):
        class_data = self.scene.get_current_class()
        if not class_data:
            return

        if key == Qt.Key_Enter or key == Qt.Key_Return:
            closed_polygons = [polygon for polygon in self.polygons if polygon.is_closed()]
            if len(closed_polygons) == 1:
                polygon = self.scene.add_annotation_polygon(
                    closed_polygons[0].get_points(),
                    class_data,
                    True
                )
                self.scene.emit_commander_to_add(polygon.get_annotation_data())

                [self.scene.scene().removeItem(polygon) for polygon in self.polygons]

                self._finish_segmentation(polygon)
            elif len(closed_polygons) > 1:
                mask = self.scene.add_annotation_mask(
                    closed_polygons,
                    class_data,
                    self.scene.get_annotation_id()
                )
                self.scene.emit_commander_to_add(mask.get_annotation_data())

                [self.scene.scene().removeItem(polygon) for polygon in self.polygons if polygon not in closed_polygons]
                self._finish_segmentation(mask)
            else:
                return
        elif key == Qt.Key_Escape:
            self._clear_scene()
        return

    def _finish_segmentation(self, ann_object: UAnnotationItem):
        ann_object.enable_selection()
        self.polygons.clear()
        self.current_polygon = None
        self.scene.set_work_mode(EWorkMode.Viewer.value)
        self.scene.scene().update()

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, polygon):
        if polygon in self.polygons:
            self.polygons.remove(polygon)

    def on_wheel_mouse(self, scale: float):
        return

    def _clear_scene(self):
        if len(self.polygons) == 0:
            return
        [self.scene.scene().removeItem(polygon) for polygon in self.polygons if polygon and polygon.scene()]
        self.polygons.clear()
        self.current_polygon = None

    def _add_polygon_to_scene(self, start_point: QPointF, class_data) -> UAnnotationPolygon:
        new_polygon = UAnnotationPolygon(
            [start_point],
            class_data,
            0,
            self.scene.scale_factor,
            False,
            self.scene.get_image(),
            None
        )
        new_polygon.disable_selection()
        self.scene.scene().addItem(new_polygon)
        self.polygons.append(new_polygon)

        return new_polygon

