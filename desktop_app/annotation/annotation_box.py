from typing import Callable

from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QSizeF, QPointF, QObject, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QCursor, QPainterPath, QFontMetricsF, QFont, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QApplication, QGraphicsPixmapItem, QGraphicsItem

from annotation.annotation_item import QAnnotationItem
from utility import FDetectAnnotationData


class UAnnotationBox(QAnnotationItem):
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

        self.class_id, self.class_name, self.color = class_data

        self.line_width = 4
        self.draw_scale: float = 1.0

        self.set_draw_scale(scale)

        self.background_color = QColor(self.color)
        self.background_color.setAlpha(50)

        self.resizing = False
        self.resize_handle_size = 12
        self.active_handle = None

    def get_square(self):
        rect = self.rect()
        if rect.isValid() is False:
            return 0
        else:
            return rect.width() * rect.height()

    def correct_rect(self):
        rect = self.rect()
        if rect.top() > rect.bottom():
            rect = QRectF(rect.left(), rect.bottom(), rect.width(), -rect.height())
        if rect.left() > rect.right():
            rect = QRectF(rect.right(), rect.top(), -rect.width(), rect.height())

        self.setRect(rect)

    def rect(self):
        return self._rect

    def setRect(self, new_rect: QRectF):
        self._rect = new_rect

    def set_draw_scale(self, scale: float):
        if scale > 1:
            self.draw_scale = 1
        else:
            self.draw_scale = 1 / scale

    def get_resize_handles(self):
        rect = self.rect()
        line_width = int(self.line_width * self.draw_scale)
        handle_size = int(self.resize_handle_size * self.draw_scale)
        handle_margin_left = int(handle_size / 2 + line_width / 2)
        handle_margin_right = int(-handle_size / 2 + line_width / 2)
        return {
            'top_left': QRectF(rect.topLeft() + QPointF(-handle_margin_left, -handle_margin_left),
                               QSizeF(handle_size, handle_size)),
            'top_right': QRectF(rect.topRight() + QPointF(handle_margin_right, -handle_margin_left),
                               QSizeF(handle_size, handle_size)),
            'bottom_left': QRectF(rect.bottomLeft() + QPointF(-handle_margin_left, handle_margin_right),
                               QSizeF(handle_size, handle_size)),
            'bottom_right': QRectF(rect.bottomRight() + QPointF(handle_margin_right, handle_margin_right),
                               QSizeF(handle_size, handle_size)),
            'top_line': QRectF(rect.topLeft() - QPointF(0, line_width),
                               QSizeF(rect.width(), line_width)),
            'right_line': QRectF(rect.topRight(),
                               QSizeF(line_width, rect.height())),
            'bottom_line': QRectF(rect.bottomLeft(),
                               QSizeF(rect.width(), line_width)),
            'left_line': QRectF(rect.topLeft() + QPointF(-line_width, 0),
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
        self.scene().update()
        QApplication.restoreOverrideCursor()

    def boundingRect(self):
        border_width = int(self.line_width * self.draw_scale)
        handle_margin = int(self.resize_handle_size * self.draw_scale)
        margin = max(border_width, handle_margin)
        return self.rect().adjusted(-margin, -margin, margin, margin)

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
        if self.isSelected():
            # якоря для изменения размеров прямоугольника
            handles = self.get_resize_handles()
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)
            for handle in handles.values():
                painter.drawRect(handle)

            if not self.resizing:
                # текст над прямоугольником
                text = f"ID: {self.class_id}, {self.class_name}"
                font = QFont("Arial", int(16 * self.draw_scale))
                font_color = QColor(Qt.black)

                font_metrics = QFontMetricsF(font)
                text_background_rect = font_metrics.boundingRect(text)
                text_background_rect.adjust(-6, -2, 12, 4)

                top_left = self.get_resize_handles()['top_left']
                text_background_rect.moveTo(top_left.x(), top_left.y() - text_background_rect.height() - 2)

                painter.setBrush(QBrush(self.color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(text_background_rect)

                painter.setFont(font)
                painter.setPen(font_color)
                painter.drawText(text_background_rect, Qt.AlignCenter, text)
        else:
            # фон прямоугольника
            rect = self.rect()
            pen_width = self.line_width * self.draw_scale
            adjusted_rect = rect.adjusted(-pen_width // 2, -pen_width // 2, pen_width // 2, pen_width // 2)

            painter.setPen(QPen(self.color, pen_width))
            painter.setBrush(QBrush(Qt.transparent if self.isSelected() else self.background_color))
            painter.drawRect(adjusted_rect)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedChange:
            if value:
                self.setZValue(2)
            else:
                self.setZValue(1)
        if self.scene() is not None:
            self.scene().update()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene = self.scene()
            if scene is not None:
                scene.clearSelection()
            self.setSelected(True)
            self.signal_holder.select_event.emit(self)
            for name, handle in self.get_resize_handles().items():
                if name in ['top_line', 'bottom_line', 'right_line', 'left_line']:
                    expanded_handle = handle.adjusted(-self.get_line_scaled(), -self.get_line_scaled(),
                                                      self.get_line_scaled(), self.get_line_scaled())
                else:
                    expanded_handle = handle
                if expanded_handle.contains(event.pos()):
                    self.resizing = True
                    self.active_handle = name
                    break
            if self.resizing is False and self.rect().contains(event.pos()):
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
        self.scene().update()

    def mouseMoveEvent(self, event):
        if self.resizing:
            rect = self.rect()
            pos = event.pos()
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
            parent = self.parentItem()
            if parent is not None:
                parent_bounds = self.mapFromItem(parent, parent.boundingRect()).boundingRect()
                new_rect = rect.intersected(parent_bounds)
                self.setRect(new_rect)
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

        self.scene().update()

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.active_handle = None
            self.correct_rect()
            self.update()
        else:
            super().mouseReleaseEvent(event)
        self.scene().update()

    def get_line_scaled(self):
        return int(self.line_width * self.draw_scale)