from enum import Enum
from typing import Optional, TYPE_CHECKING

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSlot
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsPolygonItem, QDialog, QGraphicsItem, QGraphicsRectItem

from SAM2.sam2_net import USam2Net
from annotation.annotation_item import UAnnotationItem
from annotation.modes.abstract import UBaseAnnotationMode, EWorkMode
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QColor, QBrush, QPen, QPolygonF

from design.sam2_window import Ui_Dialog

from commander import UAnnotationSignalHolder
from supporting.functions import get_clamped_pos
from utility import FAnnotationData

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView

class ESam2TypeAnnotation(Enum):
    Points = 1
    Box = 2

class USam2Annotation(UBaseAnnotationMode):
    def __init__(self, sam2: USam2Net, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        super().__init__()
        self.scene = scene
        self.commander = commander

        self.sam2 = sam2
        self.labels: list[bool] = list()
        self.points: list[USam2Point] = list()
        self.polygons: list[USam2Polygon] = list()

        self.point_size = 6

        self.has_started = False
        self.prev_mode = EWorkMode.Viewer

        self.window: Optional[USam2ParametersWindow] = None

        self.box_start_pos: Optional[QPointF] = None
        self.box_move_pos: Optional[QPointF] = None

        self.box: Optional[QGraphicsRectItem] = None

    def start_mode(self, prev_mode: EWorkMode):
        if prev_mode in [EWorkMode.SAM2, EWorkMode.ForceDragMode] or self.has_started:
            return
        self.prev_mode = prev_mode

        self.scene.scene().clearSelection()
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()

        if not self.window:
            self.window = USam2ParametersWindow(self.scene)
            self.window.move(0, 0)
            self.window.show()

            self.window.get_event_value_changed().connect(self._handle_on_slider_value_changed)

    def end_mode(self, mode: EWorkMode):
        if mode in [EWorkMode.SAM2, EWorkMode.ForceDragMode]:
            return
        if self.has_started and mode is not EWorkMode.SAM2:
            # Здесь должна быть ошибка при изменении режима
            return

        if self.window:
            self.window.close()
            self.window = None

        self.box_start_pos = None
        self._clear_points()
        self._clear_polygons()

        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def get_previous_mode(self) -> EWorkMode | None:
        return self.prev_mode

    def refresh(self):
        self._clear_polygons()
        self._clear_points()
        pass

    def on_press_mouse(self, event: QMouseEvent | None):
        image, current_class = self.scene.get_image(), self.scene.get_current_class()

        if not image or not self.window or not self.sam2 or self.sam2.is_predicting():
            return

        cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)

        _, matrix = self.scene.get_selectable_matrix()
        if matrix is None:
            return

        if self.window.radio_points.isChecked():
            point: Optional[USam2Point] = None

            if event.button() == Qt.LeftButton:
                self.labels.append(True)
                point = USam2Point(QColor(Qt.green), self.point_size, self.scene.scale_factor, cursor_pos_image, image)
            elif event.button() == Qt.RightButton:
                self.labels.append(False)
                point = USam2Point(QColor(Qt.red), self.point_size, self.scene.scale_factor, cursor_pos_image, image)
            else:
                return

            if point is not None:
                self.points.append(point)
                self.scene.scene().addItem(point)

            to_net: list[tuple[int, int, int]] = list()
            for point, label in zip(self.points, self.labels):
                to_net.append((int(point.x()), int(point.y()), 1 if label else 0))

            point_lists = self.sam2.segment_with_points(matrix, to_net)
            self._add_polygons_from_mask(point_lists, image, current_class[2] if current_class else QColor(Qt.lightGray))
            self.window.show_parameters()
        else:
            if event.button() == Qt.LeftButton:
                if self.box:
                    return

                self.box_start_pos = cursor_pos_image
                self.box = QGraphicsRectItem(image)
                self.box.setRect(self.box_start_pos.x(), self.box_start_pos.y(), 1, 1)
                self.box.setPen(QPen(QColor(0, 255, 0), 2 * set_to_draw_scale(self.scene.scale_factor), Qt.SolidLine))
                self.box.setBrush(QColor(0, 255, 0, 40))
                self.scene.scene().addItem(self.box)

    def on_move_mouse(self, event: QMouseEvent | None):
        if self.box:
            image = self.scene.get_image()

            if not image:
                self._delete_box()
                return

            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)

            rect = QRectF(self.box_start_pos, cursor_pos_image).normalized()
            self.box.setRect(rect)

    def on_release_mouse(self, event: QMouseEvent | None):
        if event.button() == Qt.LeftButton and self.box:
            image, current_class, (_, matrix) = self.scene.get_image(), self.scene.get_current_class(), self.scene.get_selectable_matrix()

            if matrix is None or not image or not current_class:
                self._delete_box()
                return

            points_lists = self.sam2.segment_with_box(
                matrix,
                (
                    int(self.box.rect().x()),
                    int(self.box.rect().y()),
                    int(self.box.rect().x() + self.box.rect().width()),
                    int(self.box.rect().y() + self.box.rect().height())
                ),
            )

            self._delete_box()
            self._add_polygons_from_mask(points_lists, image, current_class[2] if current_class else QColor(0, 180, 0))
            if self.window:
                self.window.show_parameters()
        pass

    def on_key_press(self, key: int):
        if key == Qt.Key_Escape:
            self.scene.set_work_mode(EWorkMode.Viewer.value)
            return True
        elif key == Qt.Key_Enter or key == Qt.Key_Return:
            class_data = self.scene.get_current_class()

            if len(self.polygons) == 0 or class_data is None:
                return

            for polygon in self.polygons:
                mask = self.scene.add_annotation_mask(
                    polygon.get_points(),
                    class_data,
                    True
                )
                self.scene.emit_commander_to_add(mask.get_annotation_data())

            self._clear_polygons()
            self._clear_points()
            if self.window:
                self.window.clear_window()
            return True

    def on_key_hold(self, key: int):
        pass

    def on_key_release(self, key: int):
        pass

    def on_select_item(self, item: UAnnotationItem):
        pass

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        pass

    def on_delete_item(self, item: UAnnotationItem):
        pass

    def on_wheel_mouse(self, scale: float):
        for point in self.points:
            point.set_size(self.point_size, scale)
        for polygon in self.polygons:
            polygon.set_size(1, scale)

    def _clear_items(self, items: list):
        for item in items:
            if item.scene():
                item.scene().removeItem(item)
        items.clear()

    def _clear_polygons(self):
        if self.polygons:
            self._clear_items(self.polygons)

    def _clear_points(self):
        if self.points:
            self._clear_items(self.points)
            self.labels.clear()

    def _delete_last_point(self):
        if len(self.points) == 0:
            return

        deleted_point = self.points.pop()
        if deleted_point.scene():
            deleted_point.scene().removeItem(self.points[-1])
        self.labels.pop()

    def _delete_box(self):
        if self.box and self.box.scene():
            self.box.scene().removeItem(self.box)
        self.box = None
        self.box_start_pos = None

    def _handle_on_slider_value_changed(self, value: int):
        if len(self.polygons) == 0:
            return

        epsilon = value / 10.0
        for polygon in self.polygons:
            polygon.simplify(epsilon)

    def _add_polygons_from_mask(self, point_lists, image, color: QColor):
        self._clear_polygons()
        for point_list in point_lists:
            polygon = USam2Polygon(point_list, self.scene.scale_factor, color, image)
            self.polygons.append(polygon)
            self.scene.scene().addItem(polygon)
        self.scene.update()
        self.window.set_polygons_count(len(point_lists))

class USam2ParametersWindow(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)

        self.offset = None

        self.slider_approximation.setRange(10, 50)
        self.slider_approximation.setSingleStep(1)
        self.slider_approximation.setValue(10)

        self._hide_show(True)

        self.slider_approximation.valueChanged.connect(self.handle_slider_value_changed)

    def show_parameters(self):
        self._hide_show(False)

    def clear_window(self):
        self.label_count.setText(str(0))
        self.label_approximation.setText(str(1.0))
        self.slider_approximation.setValue(10)

        self._hide_show(True)

    def set_polygons_count(self, count: int):
        self.label_count.setText(str(count))

    def get_event_value_changed(self):
        return self.slider_approximation.valueChanged

    @pyqtSlot(int)
    def handle_slider_value_changed(self, value: int):
        self.label_approximation.setText(str(value / 10.0))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == Qt.LeftButton:
            new_pos = self.mapToParent(event.pos() - self.offset)
            parent_rect = self.parent().rect()
            new_geom = self.geometry()
            new_geom.moveTopLeft(new_pos)

            if parent_rect.contains(new_geom, proper=True):
                self.move(new_pos)

    def mouseReleaseEvent(self, event):
        self.offset = None

    def _hide_show(self, to_hide: bool = True):
        if to_hide:
            self.label_count.hide()
            self.label_approximation.hide()
            self.slider_approximation.hide()
            self.button_make_polygons.hide()
            self.label_ap_text.hide()
            self.label_polygon.hide()
        else:
            self.label_count.show()
            self.label_approximation.show()
            self.slider_approximation.show()
            self.button_make_polygons.show()
            self.label_ap_text.show()
            self.label_polygon.show()

class USam2Point(QGraphicsEllipseItem):
    def __init__(self, color: QColor, size: float, scale: float, position: QPointF, parent=None):
        draw_scale = set_to_draw_scale(scale)
        scaled_size = size * draw_scale
        rect = QRectF(-scaled_size / 2, -scaled_size / 2, scaled_size, scaled_size)

        super().__init__(rect, parent)

        self.setPos(position)
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.black, draw_scale, Qt.SolidLine))

        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def set_size(self, size: float, scale: float):
        draw_scale = set_to_draw_scale(scale)
        size_scaled = size * draw_scale
        self.setPen(QPen(Qt.black, draw_scale, Qt.SolidLine))
        self.setRect(-size_scaled / 2, -size_scaled / 2, size_scaled, size_scaled)

    def get_position(self) -> tuple[float, float]:
        return self.pos().x(), self.pos().y()

class USam2Polygon(QGraphicsPolygonItem):
    def __init__(self, points: list[QPointF], scale: float, color: QColor, parent=None):
        self.original_points = points
        self.current_points = points

        super().__init__(QPolygonF(self.original_points), parent)

        self.color = color
        self.color_background = QColor(self.color)
        self.color_background.setAlpha(100)

        self.draw_scale = set_to_draw_scale(scale)
        self.size = 2

        self.setBrush(QBrush(self.color_background))
        self.setPen(QPen(self.color, scale, Qt.SolidLine))

        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def set_color(self, color: QColor):
        self.color = QColor(color)
        self.color_background = QColor(self.color)
        self.color_background.setAlpha(100)
        self.setBrush(QBrush(self.color_background))
        self.setPen(QPen(self.color, self.size * self.draw_scale, Qt.SolidLine))

    def set_size(self, size: float, scale: float):
        self.size = size
        self.draw_scale = set_to_draw_scale(scale)
        self.setPen(QPen(self.color, self.size * self.draw_scale, Qt.SolidLine))

    def simplify(self, epsilon: float):
        if epsilon <= 0 or len(self.original_points) < 3:
            return

        contour = np.array([[pt.x(), pt.y()] for pt in self.original_points], dtype=np.float32)
        contour = contour.reshape((-1, 1, 2))
        approx = cv2.approxPolyDP(contour, epsilon, True)

        self.current_points = [QPointF(float(pt[0][0]), float(pt[0][1])) for pt in approx]
        self.setPolygon(QPolygonF(self.current_points))

    def get_points(self):
        return self.current_points

def set_to_draw_scale(scale: float) -> float:
    if scale > 1:
        draw_scale = 1
    else:
        draw_scale = 1 / scale
    return draw_scale
