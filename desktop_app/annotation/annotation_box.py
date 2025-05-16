from typing import Callable

from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QSizeF, QPointF, QObject, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QCursor, QPainterPath, QFontMetricsF, QFont, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QApplication, QGraphicsPixmapItem

from utility import FDetectAnnotationData

class UAnnotationSignal(QObject):
    select_event = pyqtSignal(object)

class UAnnotationBox(QGraphicsRectItem):
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
        super().__init__(parent)

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable
        )

        self.setAcceptHoverEvents(True)
        self.isActive = True

        self.signal_holder = UAnnotationSignal()

        self.setRect(x1, y1, width, height)
        self.class_id, self.class_name, self.color = class_data

        self.line_width = 4
        self.draw_scale: float = 1.0

        self.set_draw_scale(scale)

        #self.setPen(QPen(self.color, self.line_width, Qt.SolidLine))

        self.background_color = QColor(self.color)
        self.background_color.setAlpha(50)
        self.setBrush(QBrush(self.background_color))

        self.resizing = False
        self.resize_handle_size = 12
        self.active_handle = None

    def get_square(self):
        rect = self.rect()
        if rect.isValid() is False:
            return 0
        else:
            return rect.width() * rect.height()

    def on_ctrl_pressed(self, key: int):
        if key == Qt.Key_Control and self.isActive == True:
            self.disable_selection()

    def on_ctrl_release(self, key: int):
        if key == Qt.Key_Control and self.isActive == True:
            self.enable_selection()

    def disable_selection(self):
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)
        QApplication.restoreOverrideCursor()

    def enable_selection(self):
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self.setAcceptHoverEvents(True)

    def correct_rect(self):
        rect = self.rect()
        if rect.top() > rect.bottom():
            rect = QRectF(rect.left(), rect.bottom(), rect.width(), -rect.height())
        if rect.left() > rect.right():
            rect = QRectF(rect.right(), rect.top(), -rect.width(), rect.height())

        self.setRect(rect)

    def set_draw_scale(self, scale: float):
        if scale > 1.0:
            self.draw_scale = 1.0
        else:
            self.draw_scale = 1.0 / scale

    def get_resize_handles(self):
        rect = self.rect()
        handle_size = int(self.resize_handle_size * self.draw_scale)
        line_width = int(self.line_width * self.draw_scale)
        return {
            'top_left': QRectF(rect.topLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_right': QRectF(rect.topRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_left': QRectF(rect.bottomLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_right': QRectF(rect.bottomRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_line': QRectF(rect.topLeft() - QPointF(line_width, line_width),
                               QSizeF(rect.width() + line_width, line_width)),
            'right_line': QRectF(rect.topRight() - QPointF(line_width, line_width),
                               QSizeF(line_width, rect.height() + line_width)),
            'bottom_line': QRectF(rect.bottomLeft() - QPointF(line_width, line_width),
                               QSizeF(rect.width() + line_width, line_width)),
            'left_line': QRectF(rect.topLeft() - QPointF(line_width, line_width),
                               QSizeF(line_width, rect.height() + line_width)),
        }

    @staticmethod
    def get_resize_cursor(active_handle : str):
        if active_handle in UAnnotationBox.resize_cursors:
            return UAnnotationBox.resize_cursors[active_handle]
        else:
            return 'default'

    def update_annotate_class(self, data: tuple[int, str, QColor]):
        self.class_id, self.class_name, self.color = data

        self.background_color = QColor(self.color)
        self.background_color.setAlpha(50)

        self.update()

    def x(self):
        return (self.pos() + self.rect().topLeft()).x()

    def y(self):
        return (self.pos() + self.rect().topLeft()).y()

    def width(self):
        return self.rect().width()

    def height(self):
        return self.rect().height()

    def resolution_width(self):
        if self.parentItem() and isinstance(self.parentItem(), QGraphicsPixmapItem):
            return self.parentItem().boundingRect().width()
        else:
            return 0

    def resolution_height(self):
        if self.parentItem() and isinstance(self.parentItem(), QGraphicsPixmapItem):
            return self.parentItem().boundingRect().height()
        else:
            return 0

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

    def get_class_name(self):
        return self.class_name

    def get_class_id(self):
        return self.class_id

    def get_color(self):
        return QColor(self.color)

    def connect_selected_signal(self, func: Callable[[object], None]):
        self.signal_holder.select_event.connect(func)

    def hoverMoveEvent(self, event):
        for name, handle in self.get_resize_handles().items():
            if handle.contains(event.pos()):
                cursor = QCursor(UAnnotationBox.get_resize_cursor(name))
                current_cursor = QApplication.overrideCursor()
                if current_cursor:
                    if current_cursor.shape() == cursor.shape():
                        pass
                    else:
                        QApplication.restoreOverrideCursor()
                        QApplication.setOverrideCursor(cursor)
                else:
                    QApplication.setOverrideCursor(cursor)
                return
            elif self.rect().contains(event.pos()):
                current_cursor = QApplication.overrideCursor()
                if current_cursor:
                    if current_cursor.shape() == QCursor(Qt.SizeAllCursor).shape():
                        pass
                    else:
                        QApplication.restoreOverrideCursor()
                        QApplication.setOverrideCursor(QCursor(Qt.SizeAllCursor))
                else:
                    QApplication.setOverrideCursor(QCursor(Qt.SizeAllCursor))
            else:
                QApplication.restoreOverrideCursor()

    def hoverLeaveEvent(self, event):
        self.scene().update()
        QApplication.restoreOverrideCursor()

    def boundingRect(self):
        border_width = int(self.line_width * self.draw_scale)
        handle_margin = int(self.resize_handle_size * self.draw_scale) if self.isSelected() else 0
        margin = max(border_width, handle_margin)
        return self.rect().adjusted(-margin, -margin, margin, margin)

    def shape(self):
        path = QPainterPath()
        border_width = int(self.line_width * self.draw_scale)
        rect_with_margin = self.rect().adjusted(-border_width, -border_width, border_width, border_width)
        path.addRect(rect_with_margin)

        if self.isSelected():
            for handle in self.get_resize_handles().values():
                path.addRect(handle)

        return path

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            handles = self.get_resize_handles()
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)
            for handle in handles.values():
                painter.drawRect(handle)

            if not self.resizing:
                # Отрисовка текста
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
            rect = self.rect()
            pen_width = self.line_width * self.draw_scale
            adjusted_rect = rect.adjusted(-pen_width, -pen_width, pen_width, pen_width)

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
                if handle.contains(event.pos()):
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
            self.setRect(rect)
        else:
            if self.rect().contains(event.pos()):
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