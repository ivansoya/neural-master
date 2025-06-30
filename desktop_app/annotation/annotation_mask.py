from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsItem

from annotation.annotation_item import UAnnotationItem
from annotation.annotation_polygon import UAnnotationPolygon
from utility import FPolygonAnnotationData, FDetectAnnotationData


class UAnnotationMask(UAnnotationItem):
    def __init__(
            self,
            polygons: list[UAnnotationPolygon],
            class_data: tuple[int, str, QColor],
            scale: float,
            annotation_id: int,
            parent=None
    ):
        self.polygons: list[UAnnotationPolygon] = polygons

        super().__init__(class_data, scale, parent)

        self.annotation_id = annotation_id
        [polygon.set_mask(self) for polygon in self.polygons]

        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        # переменны для отображения
        self.padding = 2
        self.border_width = 1

    def add_polygon(self, polygon: UAnnotationPolygon):
        polygon.set_class_data(
            (self.class_id, self.class_name, QColor(self.color))
        )
        polygon.set_mask(self)
        polygon.turn_off_signal_holder()
        self.polygons.append(polygon)

    def remove_polygon(self, polygon: UAnnotationPolygon):
        if polygon in self.polygons:
            self.polygons.remove(polygon)
        return polygon

    def on_select_polygon(self, polygon: UAnnotationPolygon, is_selected: bool):
        selected_count = sum([poly.isSelected() for poly in self.polygons])
        print(f"Сработал сигнал выделения полигона, {selected_count}")
        self.signal_holder.select_event.emit(self, True if selected_count > 0 else False)

    def on_update_polygon(self, polygon: UAnnotationPolygon, prev_data: list[QPointF], current_data: list[QPointF]):
        self.signal_holder.update_event.emit(self, None, self.get_annotation_data())

    def on_delete_polygon(self, polygon: UAnnotationPolygon):
        if polygon in self.polygons:
            if polygon.scene():
                polygon.scene().removeItem(polygon)
            self.polygons.remove(polygon)
        if len(self.polygons) == 0:
            self.signal_holder.delete_event.emit(self)
        else:
            self.signal_holder.update_event.emit(self, None, self.get_annotation_data())
        self.update()

    def delete_item(self):
        self.polygons.clear()

    def x(self):
        return self.rect().x()

    def y(self):
        return self.rect().y()

    def width(self):
        return self.rect().width()

    def height(self):
        return self.rect().height()

    def set_draw_scale(self, scale: float):
        for polygon in self.polygons:
            polygon.set_draw_scale(scale)
        super().set_draw_scale(scale)

    def change_activity_mode(self, status: bool):
        for polygon in self.polygons:
            polygon.change_activity_mode(status)

    def boundingRect(self) -> QRectF:
        if not self.polygons:
            return QRectF()

        rect = self.polygons[0].boundingRect().translated(self.polygons[0].pos())
        for poly in self.polygons[1:]:
            rect = rect.united(poly.boundingRect().translated(poly.pos()))

        return rect.adjusted(-5, -20, 5, 5)

    def rect(self) -> QRectF:
        if not self.polygons:
            return QRectF()

        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        for poly in self.polygons:
            for point in poly.get_points():
                min_x = min(min_x, point.x())
                max_x = max(max_x, point.x())
                min_y = min(min_y, point.y())
                max_y = max(max_y, point.y())

        if min_x == float('inf') or min_y == float('inf'):
            return QRectF()

        return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))

    def get_annotation_data(self) -> FDetectAnnotationData:
        box = self.rect()
        parent_bounds = self.parentItem().boundingRect() if self.parentItem() else QRectF()
        return FDetectAnnotationData(
            box.x(),
            box.y(),
            box.width(),
            box.height(),
            self.annotation_id,
            self.class_id,
            self.class_name,
            self.color,
            parent_bounds.width(),
            parent_bounds.height(),
        )

    def paint(self, painter, option, widget = ...):
        if len(self.polygons) == 0:
            return

        any_selected = any(polygon.isSelected() for polygon in self.polygons)

        scaled_padding = self.padding * self.draw_scale
        rect_draw = self.rect().adjusted(-scaled_padding, -scaled_padding, scaled_padding, scaled_padding)

        pen = QPen(QColor(self.color.red(), self.color.green(), self.color.blue(), 100) if any_selected else self.color)
        pen.setWidth(int(self.border_width * self.draw_scale))
        pen.setStyle(Qt.DashLine if any_selected else Qt.SolidLine)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect_draw)

        if any_selected:
            self.paint_text(painter, rect_draw.topLeft() - QPointF(0, scaled_padding))


