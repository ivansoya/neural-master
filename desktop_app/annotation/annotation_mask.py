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
            self.setPos(cursor_pos)
        event.accept()

class UAnnotationPointStart(UAnnotationPoint):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(index, cords, size, scale, parent)
        self.setAcceptHoverEvents(True)

        self.default_brush = QBrush(Qt.white)
        self.hover_brush = QBrush(Qt.green)

        self.setBrush(self.default_brush)
        self.is_hovered = False

    @classmethod
    def from_point(cls, point: 'UAnnotationPoint') -> 'UAnnotationPointStart':
        new_point = cls(
            point.index,
            point.center,
            point.size,
            point.draw_scale,
            point.parent
        )
        return new_point

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

    def mouseMoveEvent(self, event):
        return super().mouseMoveEvent(event)


class UMaskEmitter(QObject):
    deleted = pyqtSignal(object)


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

        self.points_size: int = 8
        self.line_width: int = 2

        self.points: list[QPointF] = list_points
        if self.points and len(self.points) > 0:
            self.move_point = self.points[-1]
        else:
            self.move_point = None
        self.closed = False

        self._emitter = UMaskEmitter()

    def connect_to_delete_signal(self, func: Callable[[object], None]):
        self._emitter.deleted.connect(func)

    def update_point(self, index: int, new_pos: QPointF):
        if not (0 <= index < len(self.points)):
            return

        parent = self.parentItem()
        if isinstance(parent, QGraphicsPixmapItem):
            max_x = parent.boundingRect().width()
            max_y = parent.boundingRect().height()

            new_pos.setX(clamp(new_pos.x(), 0, max_x))
            new_pos.setY(clamp(new_pos.y(), 0, max_y))

        self.points[index] = QPointF(new_pos)
        self.update()

    def add_point(self, new_point: QPointF):
        self.points.append(QPointF(new_point))

    def move(self, new_point: QPointF):
        self.move_point = QPointF(new_point)

    def fix_point(self) -> bool:
        ret = self._check_point_to_fix(self.move_point)
        if ret == 2:
            self.close()
            return True
        elif ret == 1:
            if self.isSelected():
                point = UAnnotationPoint(
                    len(self.points),
                    self.move_point,
                    self.points_size,
                    self.draw_scale,
                    self
                )
                self.scene().addItem(point)
                self.graphics_points_list.append(point)
            self.points.append(QPointF(self.move_point))
            return False

    def close(self):
        self.closed = True

    # Удаление точки у маски
    def remove_point(self, index: int):
        if not 0 <= index < len(self.points):
            return

        deleted_point = self.points.pop(index)
        if 0 <= index < len(self.graphics_points_list):
            graph_delete = self.graphics_points_list.pop(index)
            self.scene().removeItem(graph_delete)

        if (len(self.points) <= 2 and self.closed) or len(self.points) == 0:
            self._emitter.deleted.emit(self)
            return

        self._check_point_start()

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
        if len(self.points) == 0:
            return QRectF()

        polygon = QPolygonF(self.points) if self.closed else QPolygonF(self.points + [self.move_point] if self.move_point else [])
        return polygon.boundingRect().adjusted(-self.points_size, -self.points_size, self.points_size, self.points_size)

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
        self._del_children()
        if len(self.points) == 0:
            return

        for p_index in range(len(self.points)):
            if p_index == 0 and not self.closed:
                temp = UAnnotationPointStart(p_index, self.points[p_index], self.points_size, self.draw_scale, self)
            else:
                temp = UAnnotationPoint(p_index, self.points[p_index], self.points_size, self.draw_scale, self)
            self.scene().addItem(temp)
            self.graphics_points_list.append(temp)

    def paint(self, painter, option, widget = ...):
        scaled_line_width = int(self.line_width * self.draw_scale)
        painter.setPen(QPen(self.color, scaled_line_width))
        if self.is_closed():
            fill_color = QColor(self.color)
            fill_color.setAlpha(100)
            painter.setBrush(QBrush(fill_color, Qt.SolidPattern))
            painter.drawPolygon(QPolygonF(self.points))
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(QPolygonF(self.points + [self.move_point] if self.move_point else []))

    def set_draw_scale(self, scale: float):
        if scale > 1:
            self.draw_scale = 1
        else:
            self.draw_scale = 1 / scale

        for point in self.graphics_points_list:
            point.set_scale(self.draw_scale)

    def delete_mask(self):
        self._del_children()
        self.points.clear()

    def _del_children(self):
        for point in self.graphics_points_list:
            if point and point.scene():
                self.scene().removeItem(point)
        self.graphics_points_list.clear()

    def get_annotation_data(self):
        if not self.closed or self.parentItem() is None:
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

    def _check_point_to_fix(self, check_point: QPointF):
        def rect_with_center(point_t):
            rect = QRectF(point_t.boundingRect())
            rect.moveCenter(point_t.get_center())
            return rect

        if self.closed is True:
            return 0

        if len(self.graphics_points_list) == 0:
            return 1

        if self.graphics_points_list[0] and rect_with_center(self.graphics_points_list[0]).contains(check_point):
            return 2

        for point in self.graphics_points_list[1:]:
            if point and rect_with_center(point).contains(check_point):
                return 0

        return 1

    def _check_point_start(self):
        if len(self.points) == 0 or len(self.graphics_points_list) == 0:
            return

        current_start = self.graphics_points_list[0]
        if not isinstance(current_start, UAnnotationPointStart):
            return

        new_start_point = UAnnotationPointStart.from_point(current_start)

        self.scene().removeItem(current_start)
        self.graphics_points_list[0] = new_start_point
        self.scene().addItem(new_start_point)

