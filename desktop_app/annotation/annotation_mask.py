from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

from annotation.annotation_item import UAnnotationItem
from annotation.annotation_polygon import UAnnotationPolygon
from utility import FAnnotationItem, FAnnotationData


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

        super().__init__(class_data, annotation_id, scale, parent)

        for polygon in self.polygons:
            polygon.set_mask(self)
            polygon.set_annotation_id(self.annotation_id)

        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        # переменные для отображения
        self.padding = 2
        self.border_width = 1

    def add_polygon(self, polygon: UAnnotationPolygon):
        polygon.set_class_data(
            (self.class_id, self.class_name, QColor(self.color))
        )
        polygon.set_mask(self)
        polygon.turn_off_signal_holder()
        self.polygons.append(polygon)

    def create_polygon(self, points: list[QPointF]):
        if not self.scene():
            return

        polygon = UAnnotationPolygon(
            points,
            (self.class_id, self.class_name, QColor(self.color)),
            self.annotation_id,
            self.draw_scale,
            True,
            self.parentItem() if isinstance(self.parentItem(), QGraphicsPixmapItem) else None,
            self
        )
        self.scene().addItem(polygon)
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
        self.update()

    def on_update_polygon(self, polygon: UAnnotationPolygon, prev_data: list[QPointF], current_data: list[QPointF]):
        print("Обновление полигона!")
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

    def class_data(self):
        return self.class_id, self.class_name, self.color

    def update_annotate_class(self, data: tuple[int, str, QColor]):
        super().update_annotate_class(data)

        for polygon in self.polygons:
            polygon.set_class_data(data)

    def set_draw_scale(self, scale: float):
        for polygon in self.polygons:
            polygon.set_draw_scale(scale)
        super().set_draw_scale(scale)

    def disable_selection(self):
        for polygon in self.polygons:
            polygon.disable_selection()

    def enable_selection(self):
        for polygon in self.polygons:
            polygon.enable_selection()

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

        x_cords = [point.x() for polygon in self.polygons for point in polygon.get_points()]
        y_cords = [point.y() for polygon in self.polygons for point in polygon.get_points()]

        min_x, max_x = min(x_cords), max(x_cords)
        min_y, max_y = min(y_cords), max(y_cords)

        return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))

    def get_segmentation(self) -> list:
        return [
                    [coord for point in polygon.get_points() for coord in (point.x(), point.y())]
                    for polygon in self.polygons
               ]

    def get_annotation_data(self) -> FAnnotationData:
        box = self.rect()
        parent_bounds = self.parentItem().boundingRect() if self.parentItem() else QRectF()
        return FAnnotationData(
            self.annotation_id,
            [box.x(), box.y(), box.width(), box.height()],
            self.get_segmentation(),
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


