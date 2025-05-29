from typing import Callable

from PyQt5.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject, QRect
from PyQt5.QtGui import QColor, QPolygonF, QPainterPath, QPainterPathStroker, QBrush, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItem, QWidget

from annotation.annotation_item import UAnnotationItem
from supporting.functions import clamp
from utility import FSegmentationAnnotationData


class UAnnotationPoint(QGraphicsRectItem):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(parent)
        self.parent = parent if isinstance(parent, UAnnotationMask) else None

        self.setFlag(QGraphicsRectItem.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable)
        self.setAcceptHoverEvents(False)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

        self.color_handle = QColor(Qt.white)
        self.color_pen = QColor(Qt.black)
        self.width_pen = 1

        self.size = size
        self.draw_scale = scale

        self.index = index
        self.center = QPointF(cords)

        if self.parent:
            # `cords` в координатах изображения => нужно перевести в координаты self.parent
            local_pos = self.parent.mapFromScene(self.parent.mapToScene(cords))
            self.setPos(local_pos)
        else:
            self.setPos(cords)  # если нет родителя — координаты сцены

        print("Координаты начала хуйни: ", self.center)

        self.setZValue(10)

    def paint(self, painter, option, widget=None):
        size = int(self.size * self.draw_scale)
        painter.setPen(QPen(QColor(Qt.black), int(self.width_pen * self.draw_scale)))
        painter.setBrush(QColor(Qt.white))
        painter.drawRect(QRectF(-size / 2, -size / 2, size, size))

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def set_scale(self, scale: float):
        self.draw_scale = scale

    def boundingRect(self):
        return (QRectF(-self.size / 2, -self.size / 2, self.size, self.size)
                .adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen)
                )

    def mousePressEvent(self, event):
        event.accept()
        if event.button() == Qt.RightButton:
            if self.parent:
                self.parent.remove_point(self.index)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.parent and self.parent.parentItem():
                cursor_pos = self.mapToItem(self.parent.parentItem(), event.pos())
                valid_pos = self.parent.update_point(self.index, cursor_pos)
                if valid_pos:
                    self.setPos(valid_pos)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.parent and self.parent.parentItem():
            cursor_pos = self.mapToItem(self.parent.parentItem(), event.pos())
            self.parent.update_point(self.index, cursor_pos)
        event.accept()

class UAnnotationPointStart(UAnnotationPoint):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(index, cords, size, scale, parent)
        self.setAcceptHoverEvents(True)

        self.default_brush = QBrush(Qt.white)
        self.hover_brush = QBrush(Qt.green)

        self.setBrush(self.default_brush)
        self.is_hovered = False

    def paint(self, painter, option, widget=None):
        size = int(self.size * self.draw_scale)
        painter.setPen(QPen(QColor(Qt.black), self.width_pen))
        painter.setBrush(QColor(Qt.white))
        painter.drawRect(self.boundingRect())

    def boundingRect(self):
        if self.is_hovered:
            scale = int(self.draw_scale * self.size)
            return super().boundingRect().adjusted(-scale / 2, -scale / 2, scale, scale)
        else:
            return super().boundingRect()

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()
        if isinstance(self.parent, UAnnotationMask):
            polygon = self.parent.get_polygon()
            if polygon.size() > 3:
                self.parent.update_point(polygon.size() - 1, self.center)
                print(self.center, " Вот координаты начала!")
                if self.parent.is_closed():
                    self.parent.get_emitter().closed_polygon.emit()
            self.parent.get_emitter().deleted_mask.emit(self.parent)


class UMaskEmitter(QWidget):
    deleted_mask = pyqtSignal(object)
    closed_polygon = pyqtSignal()

    def __init__(self):
        super().__init__()


class UAnnotationMask(UAnnotationItem):
    def __init__(
            self,
            list_points: list[QPointF],
            class_data: tuple[int, str, QColor],
            scale: float = 1.0,
            parent = None
    ):
        self.graphics_points_list: list[UAnnotationPoint] = list()

        super().__init__(class_data, scale, parent)

        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

        self._emitter = UMaskEmitter()

        self.polygon = QPolygonF()
        for point in list_points:
            self.polygon.append(point)

        self.points_size: int = 8
        self.line_width: int = 2

    def update_point(self, index: int, new_pos: QPointF) -> QPointF | None:
        if not (0 <= index < len(self.polygon)):
            return None

        parent = self.parentItem()
        if isinstance(parent, QGraphicsPixmapItem):
            max_x = parent.boundingRect().width()
            max_y = parent.boundingRect().height()

            new_pos.setX(clamp(new_pos.x(), 0, max_x))
            new_pos.setY(clamp(new_pos.y(), 0, max_y))

        self.polygon.replace(index, new_pos)
        self.update()
        return new_pos

    def add_point(self):
        self.polygon.append(self.polygon.last())

    def fix_point(self, pos: QPointF) -> (bool, 'UAnnotationMask'):
        if self.polygon.last() and self._check_points(pos, self.points_size):
            point = UAnnotationPoint(
                self.get_last_index(),
                pos,
                self.points_size,
                self.draw_scale,
                self
            )
            self.scene().addItem(point)
            self.graphics_points_list.append(point)
            return True
        else:
            return False

    def close_polygon(self):
        if self.polygon.size() >= 3:
            self.polygon.append(self.polygon.first())
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def remove_point(self, index: int):
        if index < 0 or index >= self.polygon.size():
            return
        was_closed = self.is_closed()

        if index == 0:
            self.polygon.remove(self.polygon.size() - 1)  # удаляем "замыкающую" точку
        self.polygon.remove(index)
        try:
            graphic_point = self.graphics_points_list.pop(index)
            if graphic_point:
                self.scene().removeItem(graphic_point)
        except Exception as error:
            print(str(error))

        if was_closed and not self.is_closed(): self.close_polygon()

    def shape(self):
        path = QPainterPath()

        if self.is_closed():
            path.addPolygon(self.polygon)

        if len(self.polygon) >= 2:
            path.moveTo(self.polygon[0])
            for pt in self.polygon[1:]:
                path.lineTo(pt)

        stroke = QPainterPathStroker()
        stroke.setWidth(self.line_width * 2)

        return stroke.createStroke(path) if not self.polygon.isClosed() else path.united(stroke.createStroke(path))

    def boundingRect(self):
        if self.polygon.isEmpty():
            return QRectF()

        bounds = self.polygon.boundingRect()
        return bounds.adjusted(-self.points_size, -self.points_size, self.points_size, self.points_size)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            if not self.scene():
                return super().itemChange(change, value)

            if self.isSelected():
                self.create_graphic_points()
            else:
                self._del_children()

        return super().itemChange(change, value)

    def create_graphic_points(self):
        points = [self.polygon[i] for i in range(self.polygon.size())]
        if len(points) == 0:
            return

        if not self.is_closed():
            point_start = UAnnotationPointStart(0, points[0], self.points_size, self.draw_scale, self)
            self.scene().addItem(point_start)
            self.graphics_points_list.append(point_start)

        points_create = points[:-1] if self.polygon.isClosed() else points[1:]
        for i in range(len(points_create)):
            point = UAnnotationPoint(i, points_create[i], self.points_size, self.draw_scale, self)
            self.scene().addItem(point)
            self.graphics_points_list.append(point)

    def paint(self, painter, option, widget = ...):
        scaled_line_width = int(self.line_width * self.draw_scale)
        painter.setPen(QPen(self.color, scaled_line_width))
        if self.is_closed():
            fill_color = QColor(self.color)
            fill_color.setAlpha(100)
            painter.setBrush(QBrush(fill_color, Qt.SolidPattern))
            painter.drawPolygon(self.polygon)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(self.polygon)

    def set_draw_scale(self, scale: float):
        if scale > 1:
            self.draw_scale = 1
        else:
            self.draw_scale = 1 / scale

        for point in self.graphics_points_list:
            point.set_scale(self.draw_scale)

    def delete_mask(self):
        self._del_children()

    def _del_children(self):
        for point in self.graphics_points_list:
            if point:
                self.scene().removeItem(point)
        self.graphics_points_list.clear()

    def get_annotation_data(self):
        if not self.parentItem() or not self.polygon.isClosed():
            return None
        return FSegmentationAnnotationData(
            1,
            [(point.x(), point.y()) for point in self.polygon],
            self.class_id,
            self.class_name,
            self.color,
            self.parentItem().boundingRect().width(),
            self.parentItem().boundingRect().height()
        )

    def rect(self):
        return self.polygon.boundingRect()

    def x(self):
        return self.polygon.boundingRect().center().x()

    def y(self):
        return self.polygon.boundingRect().center().y()

    def width(self):
        return self.polygon.boundingRect().width()

    def height(self):
        return self.polygon.boundingRect().height()

    def get_polygon(self):
        return self.polygon

    def get_last_index(self):
        return self.polygon.size() - 1

    def get_emitter(self):
        return self._emitter

    def connect_deleted_mask(self, func: Callable[[object], None]):
        self._emitter.deleted_mask.connect(func)

    def connect_closed_polygon(self, func: Callable[[], None]):
        self._emitter.closed_polygon.connect(func)

    def is_closed(self):
        if self.polygon.size() < 3:
            return False
        return self.polygon.first() == self.polygon.last()

    def _check_points(self, point_1: QPointF, radius: float):

        for point_2 in self.polygon[:-1]:
            dx = point_1.x() - point_2.x()
            dy = point_1.y() - point_2.y()
        return dx * dx + dy * dy >= radius * radius
