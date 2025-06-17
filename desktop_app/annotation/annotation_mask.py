from typing import Callable, Optional

from PyQt5.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject, QRect, QLine, QLineF
from PyQt5.QtGui import QColor, QPolygonF, QPainterPath, QPainterPathStroker, QBrush, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItem, QWidget
from sympy.physics.units import current

from annotation.annotation_item import UAnnotationItem
from supporting.functions import clamp, distance_to_line, distances_sum, distance_to_center
from utility import FSegmentationAnnotationData, FAnnotationData


class UAnnotationPoint(QGraphicsRectItem):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, mask=None, parent=None):
        super().__init__(parent)
        self.mask = mask if isinstance(mask, UAnnotationMask) else None

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
        self.setPos(cords)

        self.setZValue(10)

        self.last_pos = cords
        self.prev_data = self.mask.get_annotation_data() if self.mask else None

    def get_index(self) -> int:
        return self.index

    def set_index(self, index: int):
        self.index = index

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
        size_scaled = int(self.size * self.draw_scale) * 1.5
        return (QRectF(-size_scaled / 2, -size_scaled / 2, size_scaled, size_scaled)
                .adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen)
                )

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.mask:
                self.mask.remove_point(self.index)
        elif event.button() == Qt.LeftButton:
            self.last_pos = self.pos()
            if self.mask:
                self.prev_data = self.mask.get_annotation_data()
        event.accept()

    def mouseMoveEvent(self, event):
        new_pos = self.mapToParent(event.pos())

        if self.parentItem():
            parent_rect = self.parentItem().boundingRect()

            # Ограничение координат в пределах родителя
            new_pos.setX(clamp(new_pos.x(), parent_rect.left(), parent_rect.right()))
            new_pos.setY(clamp(new_pos.y(), parent_rect.top(), parent_rect.bottom()))

            self.setPos(new_pos)
        else:
            self.setPos(new_pos)

        if self.mask:
            self.mask.update_point(self.index, self.pos())
        self.scene().update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.last_pos != self.pos() and self.mask:
                self.mask.emit_update_event(self.mask, self.prev_data, self.mask.get_annotation_data())

    def clear(self):
        self.mask = None

class UAnnotationPointStart(UAnnotationPoint):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, mask=None, parent=None):
        super().__init__(index, cords, size, scale, mask, parent)
        self.setAcceptHoverEvents(True)

        self.default_brush = QBrush(Qt.white)
        self.hover_brush = QBrush(Qt.green)

        self.setBrush(self.default_brush)
        self.is_hovered = False

    @classmethod
    def from_point(cls, point: 'UAnnotationPoint') -> 'UAnnotationPointStart':
        new_point = cls(
            point.index,
            point.pos(),
            point.size,
            point.draw_scale,
            point.mask,
            point.parentItem(),
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
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        return super().mouseMoveEvent(event)


class UAnnotationMask(UAnnotationItem):
    def __init__(
            self,
            list_points: list[QPointF],
            class_data: tuple[int, str, QColor],
            scale: float = 1.0,
            closed = False,
            parent = None
    ):
        self.graphics_points_list: list[UAnnotationPoint] = list()

        super().__init__(class_data, scale, parent)

        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        self.points_size: int = 8
        self.line_width: int = 2

        self.points: list[QPointF] = list_points
        if self.points and len(self.points) > 0:
            self.move_point = self.points[-1]
        else:
            self.move_point = None
        self.closed: bool = closed

        self.setZValue(1)

        self.previous_data: Optional[FAnnotationData] = None

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

    def add_point(self, pos: QPointF):
        ret = self._check_between_points(pos)
        if ret is None:
            return

        prev_data = self.get_annotation_data()
        index_p1, index_p2 = ret
        self.points.insert(index_p2, QPointF(pos))
        if self.isSelected() and len(self.graphics_points_list) > 0:
            self._add_graphic_point(index_p2)
        self.signal_holder.update_event.emit(self, prev_data, self.get_annotation_data())

    def move(self, new_point: QPointF):
        self.move_point = QPointF(new_point)

    def fix_point(self) -> bool:
        ret = self._check_point_to_fix(self.move_point)
        if ret == 2:
            self.close()
            return True
        elif ret == 1:
            point = UAnnotationPoint(
                len(self.points),
                self.move_point,
                self.points_size,
                self.draw_scale,
                self,
                self.parentItem()
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

        prev_data = self.get_annotation_data()

        deleted_point = self.points.pop(index)
        if 0 <= index < len(self.graphics_points_list):
            graph_delete = self.graphics_points_list.pop(index)
            self.scene().removeItem(graph_delete)

        if (len(self.points) <= 2 and self.closed) or len(self.points) == 0:
            self.delete_item()
            return

        for index in range(len(self.graphics_points_list)):
            if 0 <= index < len(self.points):
                self.graphics_points_list[index].set_index(index)

        self.signal_holder.update_event.emit(self, prev_data, self.get_annotation_data())
        self._check_point_start()
        self.scene().update()

    def shape(self):
        path = QPainterPath()

        if self.closed:
            path.addPolygon(QPolygonF(self.points + [self.points[0]]))

            stroker = QPainterPathStroker()
            stroker.setWidth(self.line_width * 4)
            return path.united(stroker.createStroke(path))
        else:
            return path

    def rect(self):
        if not self.closed:
            return QRectF()

        return QPolygonF(self.points).boundingRect()

    def boundingRect(self):
        if len(self.points) == 0:
            return QRectF()

        polygon = QPolygonF(self.points) if self.closed else QPolygonF(self.points + [self.move_point] if self.move_point else [])
        return polygon.boundingRect().adjusted(
            -self.points_size,
            -int(self.get_text_bounding_rect().height() + self.points_size),
            int(self.get_text_bounding_rect().width() + self.points_size),
            self.points_size
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            if not self.scene():
                return super().itemChange(change, value)
            if self.isSelected():
                self.create_graphic_points()
            else:
                self.clear_graphic_points()
            self.signal_holder.select_event.emit(self)

        return super().itemChange(change, value)

    def mouseMoveEvent(self, event):
        if not isinstance(self.parentItem(), QGraphicsPixmapItem):
            return
        delta = self.mapToParent(event.pos() - event.lastPos())

        clamped_delta = self._compute_clamped_delta(delta)

        for index in range(len(self.points)):
            self.points[index] = self.points[index] + clamped_delta
            if 0 <= index < len(self.graphics_points_list):
                self.graphics_points_list[index].setPos(self.points[index])
        self.scene().update()
        event.accept()

    def mousePressEvent(self, event):
        if not self.scene():
            return

        if event.button() == Qt.LeftButton:
            if not self.isSelected():
                # Убираем выделение со всех объектов кроме масок
                if self.alt_pressed:
                    selected_items = self.scene().selectedItems()
                    for item in selected_items:
                        if not isinstance(item, UAnnotationMask):
                            item.setSelected(False)
                else:
                    self.scene().clearSelection()
                self.setSelected(True)
            # Сохранение данных для дальнейшего вызова сигнала обновления
            self.previous_data = self.get_annotation_data()

    def mouseReleaseEvent(self, event):
        if not self.scene():
            return

        if event.button() == Qt.LeftButton:
            current_data = self.get_annotation_data()
            if self.previous_data and self.previous_data != current_data:
                self.signal_holder.update_event.emit(self, self.previous_data, current_data)
            self.previous_data = None

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)

    def create_graphic_points(self):
        self.clear_graphic_points()
        if len(self.points) == 0:
            return

        for p_index in range(len(self.points)):
            if p_index == 0 and not self.closed:
                temp = UAnnotationPointStart(p_index, self.points[p_index], self.points_size, self.draw_scale, self, self.parentItem())
            else:
                temp = UAnnotationPoint(p_index, self.points[p_index], self.points_size, self.draw_scale, self, self.parentItem())
            self.scene().addItem(temp)
            self.graphics_points_list.append(temp)

    def paint(self, painter, option, widget = ...):
        if len(self.points) == 0:
            return

        scaled_line_width = int(self.line_width * self.draw_scale)
        painter.setPen(QPen(self.color, scaled_line_width))
        fill_color = QColor(self.color)
        fill_color.setAlpha(100)
        if self.is_closed():
            brush = QBrush(Qt.NoBrush) if self.isSelected() else QBrush(fill_color, Qt.SolidPattern)
            painter.setBrush(brush)
            painter.drawPolygon(QPolygonF(self.points))
            if self.isSelected():
                self.paint_text(painter, self.rect().topLeft() - QPointF(self.points_size, self.points_size * 1.5))
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

    def delete_item(self):
        self.move_point = None
        self.clear_graphic_points()
        self.points.clear()

    def clear_graphic_points(self):
        for point in self.graphics_points_list:
            if point is not None:
                try:
                    if point.scene():
                        point.scene().removeItem(point)
                        point.clear()
                except RuntimeError:
                    pass
        self.graphics_points_list.clear()

    def get_annotation_data(self):
        if not self.closed or self.parentItem() is None:
            return None
        return FSegmentationAnnotationData(
            [(point.x(), point.y()) for point in self.points],
            1,
            self.class_id,
            self.class_name,
            self.color,
            self.parentItem().boundingRect().width(),
            self.parentItem().boundingRect().height()
        )

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

    def _add_graphic_point(self, index: int):
        graphic_point = UAnnotationPoint(index, self.points[index], self.points_size, self.draw_scale, self, self.parentItem())
        self.scene().addItem(graphic_point)
        self.graphics_points_list.insert(index, graphic_point)
        for point in self.graphics_points_list[index + 1:]:
            point.set_index(point.get_index() + 1)
        return graphic_point

    def _check_point_to_fix(self, check_point: QPointF):
        def rect_with_center(point_t):
            rect = QRectF(point_t.boundingRect())
            rect.moveCenter(point_t.pos())
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
        if len(self.graphics_points_list) == 0 or self.closed:
            return

        current_start = self.graphics_points_list[0]
        if not isinstance(current_start, UAnnotationPointStart):
            return

        new_start_point = UAnnotationPointStart.from_point(current_start)

        self.scene().removeItem(current_start)
        self.graphics_points_list[0] = new_start_point
        self.scene().addItem(new_start_point)

    def _compute_clamped_delta(self, delta: QPointF) -> QPointF:
        img_rect = QRectF(0, 0, self.parentItem().boundingRect().width(), self.parentItem().boundingRect().height())
        bbox = self.rect()

        bbox.setTopLeft(
            QPointF(
                clamp(bbox.x() + delta.x(), 0, img_rect.width() - bbox.width()),
                clamp(bbox.y() + delta.y(), 0, img_rect.height() - bbox.height())
            )
        )

        return bbox.topLeft() - self.rect().topLeft()

    def _check_between_points(self, cursor_pos: QPointF) -> Optional[tuple[int, int]]:
        if not self.closed:
            return None

        polygon = self.points + [self.points[0]]
        min_distance: Optional[float] = None
        min_p1, min_p2 = 0, 1
        for i in range(len(polygon) - 1):
            point_1 = polygon[i]
            point_2 = polygon[i + 1]

            line = QLineF(point_1, point_2)
            distance = distance_to_center(cursor_pos, line)
            if min_distance is None: min_distance = distance
            if distance < min_distance:
                min_distance = distance
                min_p1, min_p2 = i, i + 1

        return min_p1, 0 if polygon[min_p2] == polygon[0] else min_p2



