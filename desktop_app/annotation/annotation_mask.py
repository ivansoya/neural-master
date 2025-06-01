from typing import Callable, Optional

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

    def get_center(self):
        return self.center

    def boundingRect(self):
        size_scaled = int(self.size * self.draw_scale)
        return (QRectF(-size_scaled / 2, -size_scaled / 2, size_scaled, size_scaled)
                .adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen)
                )

    def mousePressEvent(self, event):
        event.accept()
        if event.button() == Qt.RightButton:
            if self.parent:
                self.parent.remove_point(self.index)

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
        painter.setPen(QPen(QColor(Qt.black), self.width_pen))
        painter.setBrush(QColor(Qt.white))
        painter.drawRect(self.boundingRect())

    def boundingRect(self):
        if self.is_hovered:
            scale = int(self.draw_scale * self.size * 0.5)
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


class UAnnotationMask(UAnnotationItem):
    def __init__(
            self,
            list_points: list[QPointF],
            class_data: tuple[int, str, QColor],
            scale: float = 1.0,
            parent=None
    ):
        self.graphics_points_list: list[UAnnotationPoint] = list()

        super().__init__(class_data, scale, parent)

        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

        self.points_size: int = 8
        self.line_width: int = 2

        self.points: list[QPointF] = list()
        self.move_point: Optional[QPointF] = None
        self.closed = False

    def update_point(self, index: int, new_pos: QPointF) -> QPointF | None:
        if not (0 <= index < len(self.points)):
            return None

        parent = self.parentItem()
        if isinstance(parent, QGraphicsPixmapItem):
            max_x = parent.boundingRect().width()
            max_y = parent.boundingRect().height()

            new_pos.setX(clamp(new_pos.x(), 0, max_x))
            new_pos.setY(clamp(new_pos.y(), 0, max_y))

        self.points[index] = QPointF(new_pos)
        self.update()
        return new_pos

    def add_point(self, pos: QPointF):
        self.points.append(QPointF(pos))

    def set_move_point(self, pos):
        self.move_point = QPointF(pos)

    def fix_point(self, pos: QPointF) -> (bool, 'UAnnotationMask'):
        ret = self._check_point_to_fix()
        if ret == 2:
            self.close_polygon()
        elif ret == 1:
            point = UAnnotationPoint(
                self.get_last_index(),
                pos,
                self.points_size,
                self.draw_scale,
                self
            )
            self.scene().addItem(point)
            self.graphics_points_list.append(point)

        return ret

    def close_polygon(self):
        self.closed = True

    # Функция удаляет точку по индексу,
    # Возвращает истину, если маски после этого удаления уже не должно существовать
    def remove_point(self, index: int) -> bool:
        if not 0 <= index < len(self.points):
            return True

        # Удаление графической точки, если такая есть
        if 0 <= index < len(self.graphics_points_list):
            if self.graphics_points_list[index].get_center() == self.points[index]:
                self.graphics_points_list.pop(index)

        self.points.pop(index)
        return False

    def shape(self):
        path = QPainterPath()

        if self.closed:
            path.addPolygon(QPolygonF(self.points))

        if len(self.points) >= 2:
            path.moveTo(self.points[0])
            for pt in self.points[1:]:
                path.lineTo(pt)

        stroke = QPainterPathStroker()
        stroke.setWidth(self.line_width * 2)

        return stroke.createStroke(path) if not self.closed else path.united(stroke.createStroke(path))

    def boundingRect(self):
        if len(self.points):
            return QRectF()

        bounds = QPolygonF(self.points).boundingRect()
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
        if len(self.points) == 0:
            return

        for index in range(len(self.points)):
            if index == 0 and not self.closed:
                point = UAnnotationPointStart(index, self.points[index], self.points_size, self.draw_scale, self)
            else:
                point = UAnnotationPoint(index, self.points[index], self.points_size, self.draw_scale, self)
            self.scene().addItem(point)
            self.graphics_points_list.append(point)

    def paint(self, painter, option, widget=...):
        scaled_line_width = int(self.line_width * self.draw_scale)
        painter.setPen(QPen(self.color, scaled_line_width))
        if self.closed:
            fill_color = QColor(self.color)
            fill_color.setAlpha(100)
            painter.setBrush(QBrush(fill_color, Qt.SolidPattern))
            painter.drawPolygon(self.points)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(list(self.points + self.move_point))

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
        if not self.parentItem() or not self.closed:
            return None
        return FSegmentationAnnotationData(
            1,
            [(point.x(), point.y()) for point in self.points],
            self.class_id,
            self.class_name,
            self.color,
            self.parentItem().boundingRect().width(),
            self.parentItem().boundingRect().height()
        )

    def rect(self):
        return QPolygonF(self.points).boundingRect()

    def x(self):
        return QPolygonF(self.points).boundingRect().center().x()

    def y(self):
        return QPolygonF(self.points).boundingRect().center().y()

    def width(self):
        return QPolygonF(self.points).boundingRect().width()

    def height(self):
        return QPolygonF(self.points).boundingRect().height()

    def get_polygon(self):
        return self.points

    def get_last_index(self):
        return len(self.points) - 1

    def is_closed(self):
        return self.closed

    def _check_point_to_fix(self):
        def rect_with_center(point):
            rect = QRectF(point.boundingRect())
            rect.moveCenter(point.get_center())
            return rect

        if len(self.graphics_points_list) < 1 or self.move_point is None:
            return 1

        if self.graphics_points_list[0] and rect_with_center(self.graphics_points_list[0]).contains(self.move_point):
            return 2

        for point in self.graphics_points_list[1:]:
            if point and rect_with_center(point).contains(self.move_point):
                return 0

        return 1
