from abc import abstractmethod
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QBrush
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QApplication

from utility import EAnnotationType


class UAnnotationSignal(QObject):
    select_event = pyqtSignal(object, bool)
    # объект маски, предыдущая дата, текущая дата
    update_event = pyqtSignal(object, object, object)
    delete_event = pyqtSignal(object)

class UAnnotationItem(QGraphicsItem):
    def __init__(self, class_data: tuple[int, str, QColor], scale: float, parent=None):
        super().__init__(parent)

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

        self.setAcceptHoverEvents(True)

        self.class_id, self.class_name, self.color = class_data

        self.background_color: QColor = QColor(Qt.black)
        self.set_draw_scale(scale)

        self.signal_holder = UAnnotationSignal()

        self.alt_pressed = False

        self._old_pos = self.pos()
        self._old_data = None

        self.font = "Arial"
        self.font_size = 16
        self.text_padding = (-6, -2, 12, 4)

    @abstractmethod
    def get_annotation_data(self) -> 'FAnnotationData | None':
        pass

    @abstractmethod
    def x(self):
        pass

    @abstractmethod
    def y(self):
        pass

    @abstractmethod
    def width(self):
        pass

    @abstractmethod
    def height(self):
        pass

    @abstractmethod
    def rect(self):
        pass

    @abstractmethod
    def boundingRect(self):
        pass

    @abstractmethod
    def delete_item(self):
        pass

    @abstractmethod
    def get_bbox(self) -> tuple[float, float, float, float]:
        pass

    @abstractmethod
    def get_segmentation(self) -> list:
        pass

    @abstractmethod
    def get_area(self) -> float:
        pass

    def change_activity_mode(self, status: bool):
        self.setAcceptedMouseButtons(Qt.AllButtons if status is True else Qt.NoButton)
        self.setAcceptHoverEvents(status)

    def set_class_data(self, class_data: tuple[int, str, QColor]):
        self.class_id, self.class_name, self.color = class_data

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            if value:
                self.setZValue(5)
            else:
                self.setZValue(1)
        return super().itemChange(change, value)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self.alt_pressed = True
            print('Alt pressed')

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self.alt_pressed = False

    def paint_text(self, painter, point_start: QPointF):
        text = f"ID: {self.class_id}, {self.class_name}"
        font = QFont(self.font, int(self.font_size * self.draw_scale))
        font_color = QColor(Qt.black)

        font_metrics = QFontMetricsF(font)
        text_background_rect = font_metrics.boundingRect(text)
        text_background_rect.adjust(*self.text_padding)
        text_background_rect.moveTo(point_start.x(), point_start.y() - text_background_rect.height() - 2)

        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(text_background_rect)

        painter.setFont(font)
        painter.setPen(font_color)
        painter.drawText(text_background_rect, Qt.AlignCenter, text)

    def get_text_bounding_rect(self) -> QRectF:
        text = f"ID: {self.class_id}, {self.class_name}"
        font = QFont(self.font, int(self.font_size * self.draw_scale))
        font_metrics = QFontMetricsF(font)
        text_background_rect = font_metrics.boundingRect(text)
        text_background_rect.adjust(*self.text_padding)

        return text_background_rect

    def get_class_name(self):
        return self.class_name

    def get_class_id(self):
        return self.class_id

    def get_color(self):
        return QColor(self.color)

    def resolution_width(self):
        if isinstance(self.parentItem(), QGraphicsPixmapItem):
            return self.parentItem().boundingRect().width()
        else:
            return 0

    def resolution_height(self):
        if isinstance(self.parentItem(), QGraphicsPixmapItem):
            return self.parentItem().boundingRect().height()
        else:
            return 0

    def set_draw_scale(self, scale: float):
        if scale > 1:
            self.draw_scale = 1
        else:
            self.draw_scale = 1 / scale

    def update_annotate_class(self, data: tuple[int, str, QColor]):
        self.class_id, self.class_name, self.color = data

        self.background_color = QColor(self.color)
        self.background_color.setAlpha(50)

        self.update()

    def connect_selected_signal(self, func: Callable[[object, bool], None]):
        self.signal_holder.select_event.connect(func)

    def connect_update_signal(self, func: Callable[[object, object, object], None]):
        self.signal_holder.update_event.connect(func)

    def connect_delete_signal(self, func: Callable[[object], None]):
        self.signal_holder.delete_event.connect(func)

    def emit_update_event(self, item, prev_data, current_data):
        self.signal_holder.update_event.emit(item, prev_data, current_data)

    def disable_selection(self):
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)
        QApplication.restoreOverrideCursor()

    def enable_selection(self):
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self.setAcceptHoverEvents(True)
