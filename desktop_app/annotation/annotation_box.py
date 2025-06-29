from typing import Callable

from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QSizeF, QPointF, QObject, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QCursor, QPainterPath, QFontMetricsF, QFont, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QApplication, QGraphicsPixmapItem, QGraphicsItem

from annotation.annotation_item import UAnnotationItem
from utility import FDetectAnnotationData


class UAnnotationBox(UAnnotationItem):
    resize_cursors = {
        'top_left': Qt.SizeFDiagCursor,
        'top_right': Qt.SizeBDiagCursor,
        'bottom_left': Qt.SizeBDiagCursor,
        'bottom_right': Qt.SizeFDiagCursor,
        'top_line': Qt.SizeVerCursor,
        'right_line': Qt.SizeHorCursor,
        'bottom_line': Qt.SizeVerCursor,
        'left_line': Qt.SizeHorCursor,
    }

    def __init__(
            self,
            x1: float,
            y1: float,
            width: float,
            height:float,
            class_data: tuple[int, str, QColor],
            scale: float = 1.0,
            parent = None
    ):
        super().__init__(class_data, scale, parent)

        self.isActive = True

        self._rect = QRectF(x1, y1, width, height)
        self.line_width = 2

        self.background_color = QColor(self.color)
        self.background_color.setAlpha(50)

        self.resizing = False
        self.resize_handle_size = 12
        self.active_handle = None

        self.prev_data = self.get_annotation_data()

    def get_square(self):
        rect = self.rect()
        if rect.isValid() is False:
            return 0
        else:
            return rect.width() * rect.height()

    def correct_rect(self, rect: QRectF) -> QRectF:
        if rect.top() > rect.bottom():
            rect = QRectF(rect.left(), rect.bottom(), rect.width(), -rect.height())
        if rect.left() > rect.right():
            rect = QRectF(rect.right(), rect.top(), -rect.width(), rect.height())
        return rect

    def rect(self):
        return self._rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self._rect = new_rect

    def get_resize_handles(self):
        rect = self.rect()
        line_width = int(self.line_width * self.draw_scale)
        handle_size = int(self.resize_handle_size * self.draw_scale)
        return {
            'top_left': QRectF(rect.topLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_right': QRectF(rect.topRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_left': QRectF(rect.bottomLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_right': QRectF(rect.bottomRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_line': QRectF(rect.topLeft() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(rect.width(), line_width)),
            'right_line': QRectF(rect.topRight() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(line_width, rect.height())),
            'bottom_line': QRectF(rect.bottomLeft() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(rect.width(), line_width)),
            'left_line': QRectF(rect.topLeft() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(line_width, rect.height())),
        }

    @staticmethod
    def get_resize_cursor(active_handle : str):
        if active_handle in UAnnotationBox.resize_cursors:
            return UAnnotationBox.resize_cursors[active_handle]
        else:
            return 'default'

    def x(self):
        return (self.pos() + self.rect().topLeft()).x()

    def y(self):
        return (self.pos() + self.rect().topLeft()).y()

    def width(self):
        return self.rect().width()

    def height(self):
        return self.rect().height()

    def get_annotation_data(self):
        try:
            return FDetectAnnotationData(
                int(self.x()),
                int(self.y()),
                int(self.width()),
                int(self.height()),
                1,
                int(self.class_id),
                str(self.class_name),
                QColor(self.color),
                int(self.parentItem().boundingRect().width()),
                int(self.parentItem().boundingRect().height())
            )
        except Exception as error:
            print(str(error))
            return None

    def hoverMoveEvent(self, event):
        # Здесь все это нужно только для смены курсоров
        pos = event.pos()
        cursor_shape = None

        for name, handle in self.get_resize_handles().items():
            # Расширение линий, как везде в коде
            if name in ['top_line', 'bottom_line', 'right_line', 'left_line']:
                expanded_handle = handle.adjusted(
                    -self.get_line_scaled(), -self.get_line_scaled(),
                    self.get_line_scaled(), self.get_line_scaled()
                )
            else:
                expanded_handle = handle
            # Взятие иконки курсора, здесь же настройка этих форм
            if expanded_handle.contains(pos):
                cursor_shape = UAnnotationBox.get_resize_cursor(name)
                break
        else:
            if self.rect().contains(pos):
                cursor_shape = Qt.SizeAllCursor

        # Смена курсора
        current_cursor = QApplication.overrideCursor()
        if cursor_shape is not None:
            if not current_cursor or current_cursor.shape() != cursor_shape:
                QApplication.restoreOverrideCursor()
                QApplication.setOverrideCursor(QCursor(cursor_shape))
        else:
            if current_cursor:
                QApplication.restoreOverrideCursor()

    def hoverLeaveEvent(self, event):
        QApplication.restoreOverrideCursor()

    def boundingRect(self):
        base_rect = self.rect().normalized()
        border_width = int(self.line_width * self.draw_scale)
        handle_margin = int(self.resize_handle_size * self.draw_scale)
        margin = max(border_width, handle_margin)

        text_background_rect = self.get_text_bounding_rect()

        return base_rect.adjusted(
            -margin,
            -margin - text_background_rect.height(),
            max(margin, text_background_rect.width() - base_rect.width() + margin),
            margin
        )

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect())
        for handle, handle_rect in self.get_resize_handles().items():
            handle_path = QPainterPath()
            # нужно, чтобы увеличить область захвата линий, типа для удобства
            if handle in ['top_line', 'bottom_line', 'right_line', 'left_line']:
                handle_path.addRect(handle_rect.adjusted(-self.get_line_scaled(), -self.get_line_scaled(),
                                                         self.get_line_scaled(), self.get_line_scaled()))
            else:
                handle_path.addRect(handle_rect)
            path = path.united(handle_path)
        return path

    def paint(self, painter, option, widget=None):
        # фон прямоугольника
        pen_width = self.line_width * self.draw_scale

        painter.setPen(QPen(self.color, pen_width))
        painter.setBrush(QBrush(Qt.transparent if self.isSelected() else self.background_color))
        painter.drawRect(self.rect())

        if self.isSelected():
            # якоря для изменения размеров прямоугольника
            handles = self.get_resize_handles()
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)
            for name, handle in handles.items():
                if name not in ['top_line', 'bottom_line', 'right_line', 'left_line']:
                    painter.drawRect(handle)

            if not self.resizing:
                # текст над прямоугольником
                self.paint_text(painter, self.get_resize_handles()['top_left'])

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.signal_holder.select_event.emit(self, self.isSelected())
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for name, handle in self.get_resize_handles().items():
                if name in ['top_line', 'bottom_line', 'right_line', 'left_line']:
                    expanded_handle = handle.adjusted(
                        -self.get_line_scaled(), -self.get_line_scaled(),
                        self.get_line_scaled(), self.get_line_scaled()
                    )
                else:
                    expanded_handle = handle

                if expanded_handle.contains(event.pos()):
                    self.resizing = True
                    self.active_handle = name
                    break

            if not self.resizing and self.rect().contains(event.pos()):
                if event.modifiers() & Qt.ControlModifier:
                    self.setSelected(not self.isSelected())
                else:
                    if self.scene():
                        self.scene().clearSelection()
                    self.setSelected(True)
                super().mousePressEvent(event)

            self.prev_data = self.get_annotation_data()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            rect = self.rect()
            pos = event.pos()

            parent = self.parentItem()
            if not parent:
                return

            parent_bounds = self.mapFromItem(parent, parent.boundingRect()).boundingRect()
            pos.setX(min(max(pos.x(), parent_bounds.left()), parent_bounds.right()))
            pos.setY(min(max(pos.y(), parent_bounds.top()), parent_bounds.bottom()))

            if self.active_handle == 'top_left':
                rect.setTopLeft(pos)
            elif self.active_handle == 'top_right':
                rect.setTopRight(pos)
            elif self.active_handle == 'bottom_left':
                rect.setBottomLeft(pos)
            elif self.active_handle == 'bottom_right':
                rect.setBottomRight(pos)
            elif self.active_handle == 'top_line':
                rect.setTop(pos.y())
            elif self.active_handle == 'right_line':
                rect.setRight(pos.x())
            elif self.active_handle == 'bottom_line':
                rect.setBottom(pos.y())
            elif self.active_handle == 'left_line':
                rect.setLeft(pos.x())

            min_size = 1.0
            if abs(rect.normalized().width()) < min_size or abs(rect.normalized().height()) < min_size:
                return

            # Сохраняем текущую ориентацию (вдруг пользователь "инвертировал" прямоугольник)
            was_inverted_x = rect.left() > rect.right()
            was_inverted_y = rect.top() > rect.bottom()

            # Ограничиваем и нормализуем
            rect = rect.normalized().intersected(parent_bounds)

            # Восстанавливаем ориентацию (инверсию)
            if was_inverted_x:
                rect = QRectF(rect.right(), rect.top(), -rect.width(), rect.height())
            if was_inverted_y:
                rect = QRectF(rect.left(), rect.bottom(), rect.width(), -rect.height())

            self.setRect(rect)
        else:
            if self.rect().contains(event.pos()):
                new_pos = self.pos() + event.scenePos() - event.lastScenePos()
                parent = self.parentItem()
                if parent is not None:
                    parent_rect = parent.mapToScene(parent.boundingRect()).boundingRect()
                    rect = self.mapToScene(self.rect()).boundingRect()
                    delta = new_pos - self.pos()

                    if rect.translated(delta).left() < parent_rect.left():
                        delta.setX(parent_rect.left() - rect.left())
                    if rect.translated(delta).right() > parent_rect.right():
                        delta.setX(parent_rect.right() - rect.right())
                    if rect.translated(delta).top() < parent_rect.top():
                        delta.setY(parent_rect.top() - rect.top())
                    if rect.translated(delta).bottom() > parent_rect.bottom():
                        delta.setY(parent_rect.bottom() - rect.bottom())

                    self.setPos(self.pos() + delta)
                else:
                    super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.resizing:
                self.resizing = False
                self.active_handle = None
                self.setRect(self.correct_rect(self.rect()))

            current_data = self.get_annotation_data()
            if current_data != self.prev_data:
                self.emit_update_event(self, self.prev_data, current_data)

    def delete_item(self):
        pass

    def get_line_scaled(self):
        return int(self.line_width * self.draw_scale) * 2