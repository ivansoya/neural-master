from typing import Callable, Optional

from PyQt5.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject, QRect, QLine, QLineF
from PyQt5.QtGui import QColor, QPolygonF, QPainterPath, QPainterPathStroker, QBrush, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItem, QWidget

from annotation.annotation_item import UAnnotationItem
from supporting.functions import clamp, distance_to_line, distances_sum, distance_to_center
from utility import FPolygonAnnotationData, FAnnotationData


class UAnnotationPoint(QGraphicsRectItem):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None,):
        super().__init__(parent)
        self.mask = parent if isinstance(parent, UAnnotationPolygon) else None

        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)

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

    def change_interactive_mode(self, is_interactive: bool):
        self.setFlag(QGraphicsRectItem.ItemIsMovable, is_interactive)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton if is_interactive else Qt.NoButton)

    def get_index(self) -> int:
        return self.index

    def set_index(self, index: int):
        self.index = index

    def set_scale(self, scale: float):
        self.draw_scale = scale

    def paint(self, painter, option, widget=None):
        size = int(self.size * self.draw_scale)
        painter.setPen(QPen(QColor(Qt.black), int(self.width_pen * self.draw_scale)))
        painter.setBrush(QColor(Qt.white))
        painter.drawRect(QRectF(-size / 2, -size / 2, size, size))

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def boundingRect(self):
        size_scaled = int(self.size * self.draw_scale) * 1.5
        return (QRectF(-size_scaled / 2, -size_scaled / 2, size_scaled, size_scaled)
                .adjusted(-self.width_pen, -self.width_pen, self.width_pen, self.width_pen)
                )

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.mask:
                self.mask.remove_point(self.index)
                return
        elif event.button() == Qt.LeftButton:
            self.last_pos = self.pos()
            if self.mask:
                self.prev_data = self.mask.get_annotation_data()
        event.accept()

    def mouseMoveEvent(self, event):
        new_pos = self.mask.mapToParent(self.mapToParent(event.pos()))

        image = self.mask.parentItem() if self.mask else None
        if image:
            image_rect = image.boundingRect()

            # Ограничение координат в пределах родителя
            new_pos.setX(clamp(new_pos.x(), image_rect.left(), image_rect.right()))
            new_pos.setY(clamp(new_pos.y(), image_rect.top(), image_rect.bottom()))

            self.setPos(new_pos)
        else:
            self.setPos(new_pos)

        #if self.mask:
        #    self.mask.update_point(self.index, new_pos)
        self.scene().update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.last_pos != self.pos() and self.mask:
                self.mask.emit_update_event(self.mask, self.prev_data, self.mask.get_annotation_data())

    def clear(self):
        self.mask = None

class UAnnotationPointStart(UAnnotationPoint):
    def __init__(self, index: int, cords: QPointF, size: float, scale: float, parent=None):
        super().__init__(index, cords, size, scale, parent)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
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
            point.mask
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


class UAnnotationPolygon(UAnnotationItem):
    def __init__(
            self,
            list_points: list[QPointF],
            class_data: tuple[int, str, QColor],
            scale: float = 1.0,
            closed = False,
            parent = None,
            mask = None,
    ):
        self.graphic_points: list[UAnnotationPoint] = list()

        super().__init__(class_data, scale, parent)

        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        self.points_size: int = 8
        self.line_width: int = 2

        self.closed: bool = closed
        self.mask = None

        for i, pt in enumerate(list_points):
            if not self.closed and i == 0:
                point = UAnnotationPointStart(i, pt, self.points_size, self.draw_scale, self)
            else:
                point = UAnnotationPoint(i, pt, self.points_size, self.draw_scale, self)
            self.graphic_points.append(point)

        if self.closed:
            self.change_points_visibility(False)

        self.move_point = None if self.closed else self.graphic_points[-1].pos()

        self.setZValue(1)

        self.previous_data: Optional[FAnnotationData] = None

    def get_bbox(self) -> tuple[float, float, float, float]:
        return self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height()

    def get_area(self) -> float:
        return self.rect().width() * self.rect().height()

    def update_point(self, index: int, new_pos: QPointF):
        if not (0 <= index < len(self.graphic_points)):
            return

        parent = self.parentItem()
        if isinstance(parent, QGraphicsPixmapItem):
            max_x = parent.boundingRect().width()
            max_y = parent.boundingRect().height()

            new_pos.setX(clamp(new_pos.x(), 0, max_x))
            new_pos.setY(clamp(new_pos.y(), 0, max_y))

        self.graphic_points[index].setPos(new_pos)
        self.update()

    def add_point(self, pos: QPointF):
        ret = self._check_between_points(pos)
        if ret is None:
            return

        prev_data = self.get_annotation_data()
        index_p1, index_p2 = ret

        graphic_point = UAnnotationPoint(index_p2, pos, self.points_size, self.draw_scale, self)
        graphic_point.change_interactive_mode(True)

        self.scene().addItem(graphic_point)
        self.graphic_points.insert(index_p2, graphic_point)
        for point in self.graphic_points[index_p2 + 1:]:
            point.set_index(point.get_index() + 1)

        self.signal_holder.update_event.emit(self, prev_data, self.get_annotation_data())

    def move(self, new_point: QPointF):
        self.move_point = QPointF(new_point)

    def set_mask(self, mask):
        self.mask = mask

    def fix_point(self) -> bool:
        ret = self._check_point_to_fix(self.move_point)
        if ret == 2:
            self.close()
            return True
        elif ret == 1:
            point = UAnnotationPoint(
                len(self.graphic_points),
                self.move_point,
                self.points_size,
                self.draw_scale,
                self
            )
            self.scene().addItem(point)
            self.graphic_points.append(point)
            return False

    def close(self):
        if len(self.graphic_points) >= 3:
            start_point = self.graphic_points[0]
            if isinstance(start_point, UAnnotationPointStart):
                self.scene().removeItem(start_point)
                self.graphic_points[0] = UAnnotationPoint(start_point.get_index(), start_point.pos(), self.points_size, self.draw_scale, self)
                self.graphic_points[0].change_interactive_mode(True)
                self.scene().addItem(start_point)
                self.update()
        self.closed = True

    # Удаление точки у маски
    def remove_point(self, index: int):
        if not 0 <= index < len(self.graphic_points):
            return

        prev_data = self.get_points() if self.mask else self.get_annotation_data()

        if 0 <= index < len(self.graphic_points):
            graph_delete = self.graphic_points.pop(index)
            self.scene().removeItem(graph_delete)

        if (len(self.graphic_points) <= 2 and self.closed) or len(self.graphic_points) == 0:
            self.on_delete_event()
            return

        for index in range(len(self.graphic_points)):
            self.graphic_points[index].set_index(index)

        self.on_update_event(prev_data, self.get_points() if self.mask else self.get_annotation_data())
        self._check_point_start()
        self.scene().update()

    def shape(self):
        path = QPainterPath()

        if self.closed:
            path.addPolygon(QPolygonF(self.get_points() + [self.graphic_points[0].pos()]))

            stroker = QPainterPathStroker()
            stroker.setWidth(self.line_width * 4)
            return path.united(stroker.createStroke(path))
        else:
            return path

    def rect(self):
        if not self.closed:
            return QRectF()

        return self.get_polygon().boundingRect()

    def boundingRect(self):
        if len(self.graphic_points) == 0:
            return QRectF()

        polygon = self.get_polygon() if self.closed else QPolygonF(self.get_points() + [self.move_point] if self.move_point else [])
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
            self.change_points_visibility(self.isSelected())
            self.on_select_event(self.isSelected())

        return super().itemChange(change, value)

    def mouseMoveEvent(self, event):
        if not isinstance(self.parentItem(), QGraphicsPixmapItem):
            return
        delta = self.mapToParent(event.pos() - event.lastPos())

        clamped_delta = self._compute_clamped_delta(delta)

        for index in range(len(self.graphic_points)):
            self.graphic_points[index].setPos(self.graphic_points[index].pos() + clamped_delta)
        self.scene().update()
        event.accept()

    def mousePressEvent(self, event):
        if not self.scene():
            return

        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                self.setSelected(not self.isSelected())
            else:
                super().mousePressEvent(event)
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

    """def create_graphic_points(self):
        self.clear_graphic_points()
        if len(self.points) == 0:
            return

        for p_index in range(len(self.points)):
            if p_index == 0 and not self.closed:
                temp = UAnnotationPointStart(p_index, self.points[p_index], self.points_size, self.draw_scale, self)
            else:
                temp = UAnnotationPoint(p_index, self.points[p_index], self.points_size, self.draw_scale, self)
            self.scene().addItem(temp)
            self.graphic_points.append(temp)"""

    def change_points_visibility(self, to_show: bool):
        for point in self.graphic_points:
            point.setVisible(to_show)
            point.change_interactive_mode(to_show)

    def turn_off_signal_holder(self):
        self.signal_holder.disconnect()

    def paint(self, painter, option, widget = ...):
        if len(self.graphic_points) == 0:
            return

        scaled_line_width = int(self.line_width * self.draw_scale)
        painter.setPen(QPen(Qt.NoPen) if self.mask and self.closed and not self.isSelected() else QPen(self.color, scaled_line_width))
        fill_color = QColor(self.color)
        fill_color.setAlpha(100)
        if self.is_closed():
            brush = QBrush(Qt.NoBrush) if self.isSelected() else QBrush(fill_color, Qt.SolidPattern)
            painter.setBrush(brush)
            painter.drawPolygon(self.get_polygon())
            if not self.mask and self.isSelected():
                self.paint_text(painter, self.rect().topLeft() - QPointF(self.points_size, self.points_size * 1.5))
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(QPolygonF([point.pos() for point in self.graphic_points] + [self.move_point] if self.move_point else []))

    def set_draw_scale(self, scale: float):
        if scale > 1:
            self.draw_scale = 1
        else:
            self.draw_scale = 1 / scale

        for point in self.graphic_points:
            point.set_scale(self.draw_scale)

    def delete_item(self):
        self.move_point = None
        self.on_delete_event()

    """def clear_graphic_points(self):
        for point in self.graphic_points:
            if point is not None:
                try:
                    if point.scene():
                        point.scene().removeItem(point)
                        point.clear()
                except RuntimeError:
                    pass
        self.graphic_points.clear()"""

    def get_annotation_data(self):
        if not self.closed or self.parentItem() is None:
            return None
        return FPolygonAnnotationData(
            [(point.x(), point.y()) for point in self.graphic_points],
            1,
            self.class_id,
            self.class_name,
            self.color,
            self.parentItem().boundingRect().width(),
            self.parentItem().boundingRect().height()
        )

    def x(self):
        return self.get_polygon().boundingRect().center().x()

    def y(self):
        return self.get_polygon().boundingRect().center().y()

    def width(self):
        return self.get_polygon().boundingRect().width()

    def height(self):
        return self.get_polygon().boundingRect().height()

    def get_polygon(self):
        return QPolygonF([point.pos() for point in self.graphic_points])

    def get_points(self):
        return [point.pos() for point in self.graphic_points]

    def get_last_index(self):
        return len(self.graphic_points) - 1

    def is_closed(self):
        return self.closed

    def on_delete_event(self):
        if self.mask:
            self.mask.on_delete_polygon(self)
        else:
            self.signal_holder.delete_event.emit(self)

    def on_update_event(self, prev_data: FAnnotationData | list[QPointF], current_data: FAnnotationData | list[QPointF]):
        if self.mask:
            self.mask.on_update_polygon(self, prev_data, current_data)
        else:
            self.signal_holder.update_event.emit(self, prev_data, current_data)

    def on_select_event(self, is_selected: bool):
        if self.mask:
            self.mask.on_select_polygon(self, is_selected)
        else:
            self.signal_holder.select_event.emit(self, is_selected)

    def _check_point_to_fix(self, check_point: QPointF):
        def rect_with_center(point_t):
            rect = QRectF(point_t.boundingRect())
            rect.moveCenter(point_t.pos())
            return rect

        if self.closed is True:
            return 0

        if len(self.graphic_points) == 0:
            return 1

        if self.graphic_points[0] and rect_with_center(self.graphic_points[0]).contains(check_point):
            return 2

        for point in self.graphic_points[1:]:
            if point and rect_with_center(point).contains(check_point):
                return 0

        return 1

    def _check_point_start(self):
        if len(self.graphic_points) == 0 or self.closed:
            return

        current_start = self.graphic_points[0]
        if not isinstance(current_start, UAnnotationPointStart):
            return

        new_start_point = UAnnotationPointStart.from_point(current_start)

        self.scene().removeItem(current_start)
        self.graphic_points[0] = new_start_point
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

        polygon = [point.pos() for point in self.graphic_points] + [self.graphic_points[0].pos()]
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



