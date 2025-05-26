from typing import Callable

from PyQt5.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPolygonF, QPainterPath, QPainterPathStroker, QBrush
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItem, QWidget

from annotation.annotation_item import UAnnotationItem
from supporting.functions import clamp


class UAnnotationPoint(QGraphicsRectItem):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(parent)
        self.parent = parent if isinstance(parent, UAnnotationMask) else None

        self.setFlag(QGraphicsRectItem.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsRectItem.ItemIgnoresTransformations)

        self.color_handle = QColor(Qt.white)
        self.color_pen = QColor(Qt.black)
        self.width_pen = 1

        self.size = size
        self.draw_scale = scale

        self.index = index
        self.center = cords

        self.setRect(
            self.center.x() - size / 2,
            self.center.y() - size / 2,
            size,
            size
        )

        self.setZValue(10)

    def paint(self, painter, option, widget=None):
        size = int(self.size * self.draw_scale)
        painter.setPen(QColor(Qt.black), self.width_pen)
        painter.setBrush(size)
        painter.drawRect(self.rect())

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect().adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen))
        return path

    def boundingRect(self):
        return self.rect().adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.parent:
                self.parent.remove_point(self.index)
                self.setParentItem(None)
                self.scene().removeItem(self)
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.parent and self.parent.parentItem():
                cursor_pos = self.mapToItem(self.parent.parentItem(), event.pos())
                valid_pos = self.parent.update_point(self.index, cursor_pos)
                if valid_pos:
                    self.setPos(valid_pos)
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.parent and self.parent.parentItem():
            cursor_pos = self.mapToItem(self.parent.parentItem(), event.pos())
            self.parent.update_point(self.index, cursor_pos)
        return super().mouseMoveEvent(event)


class UStartPointEmitter(QObject):
    polygon_closed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

class UAnnotationPointStart(UAnnotationPoint):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(index, cords, size, scale, parent)
        self.setAcceptHoverEvents(True)

        self.default_brush = QBrush(Qt.white)
        self.hover_brush = QBrush(Qt.green)
        self.default_rect = self.rect()

        self.setBrush(self.default_brush)
        self.setAcceptHoverEvents(True)

        self.emitter = UStartPointEmitter()

    def hoverEnterEvent(self, event):
        self.setBrush(self.hover_brush)
        resizable_value = int(self.size * 1.5 * self.draw_scale)
        self.setRect(self.default_rect.adjusted(-resizable_value, -resizable_value, resizable_value, resizable_value))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(self.default_brush)
        self.setRect(self.default_rect)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if isinstance(self.parent, UAnnotationMask):
            polygon = self.parent.get_polygon()
            if polygon.size() > 3:
                self.parent.update_point(polygon.size() - 1, self.center)
                if polygon.isClosed():
                    self.emitter.polygon_closed.emit(True)
            self.emitter.polygon_closed.emit(False)
            print("Нажата кнопка старта создания полигона!")
            event.accept()

    def connect_to_emitter(self, func: Callable[[bool],  None]):
        self.emitter.polygon_closed.connect(func)

class UMaskEmitter(QWidget):
    deleted_mask = pyqtSignal(object)

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
        super().__init__(class_data, scale, parent)

        self.emitter = UMaskEmitter()

        self.polygon = QPolygonF()
        for point in list_points:
            self.polygon.append(point)

        self.points_size: int = 8
        self.line_width: int = 2

        self.graphics_points_list: list[UAnnotationPoint] = list()

    def get_polygon(self):
        return self.polygon

    def get_last_index(self):
        return self.polygon.size() - 1

    def update_point(self, index: int, new_pos: QPointF) -> QPointF | None:
        if not self.polygon.contains(index):
            return None

        parent = self.parentItem()
        if isinstance(parent, QGraphicsPixmapItem):
            max_x = parent.boundingRect().width()
            max_y = parent.boundingRect().height()

            new_pos.setX(clamp(new_pos.x(), 0, max_x))
            new_pos.setY(clamp(new_pos.y(), 0, max_y))

        self.polygon.replace(index, new_pos)
        return new_pos

    def add_point(self):
        self.polygon.append(self.polygon.last())

    def fix_point(self, pos: QPointF) -> (bool, 'UAnnotationMask'):
        if self.polygon.last() and UAnnotationMask._check_points(self.polygon.last(), pos, self.points_size):
            point = UAnnotationPoint(
                self.get_last_index(),
                pos,
                self.points_size,
                self.draw_scale,
                self
            )
            self.scene().addItem(point)
            self.graphics_points_list.append(point)
        if self.polygon.isClosed():
            if self.polygon.size() >= 3:
                return True, self
            else:
                return True, None
        else:
            return False, None

    def close_polygon(self):
        if not self.polygon.isClosed():
            self.polygon.append(self.polygon.first())

    def remove_point(self, index: int):
        if not self.polygon.contains(index):
            return

        if index == 0:
            self.polygon.remove(self.polygon.size() - 1)  # удаляем "замыкающую" точку
        self.polygon.remove(index)

        if self.polygon.size() < 3:
            self.emitter.deleted_mask.emit(self)
        elif self.polygon.isClosed():
            self.close_polygon()

    def shape(self):
        path = QPainterPath()

        if self.polygon.isClosed():
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
                points = [self.polygon[i] for i in range(self.polygon.size())]
                if len(points) == 0:
                    return super().itemChange(change, value)

                if not self.polygon.isClosed():
                    point_start = UAnnotationPointStart(0, points[0], self.points_size, self.draw_scale, self)
                    self.scene().addItem(point_start)
                    self.graphics_points_list.append(point_start)

                points_create = points[:-1] if self.polygon.isClosed() else points[1:]
                for i in range(len(points_create)):
                    point = UAnnotationPoint(i, points_create[i], self.points_size, self.draw_scale, self)
                    self.scene().addItem(point)
                    self.graphics_points_list.append(point)
            else:
                self._del_children()

        return super().itemChange(change, value)

    def delete_mask(self):
        self._del_children()

    def _del_children(self):
        for point in self.graphics_points_list:
            if point.scene():
                point.scene().removeItem(point)
        self.graphics_points_list.clear()

    @staticmethod
    def _check_points(point_1: QPointF, point_2: QPointF, radius: float):
        dx = point_1.x() - point_2.x()
        dy = point_1.y() - point_2.y()
        return dx * dx + dy * dy <= radius * radius
