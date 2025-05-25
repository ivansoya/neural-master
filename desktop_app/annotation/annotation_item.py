from abc import abstractmethod
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QApplication


class UAnnotationSignal(QObject):
    select_event = pyqtSignal(object)
    update_event = pyqtSignal(object, object, object)


class UAnnotationItem(QGraphicsItem):
    def __init__(self, class_data: tuple[int, str, QColor], scale: float, parent=None):
        super().__init__(parent)

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

        self.setAcceptHoverEvents(True)

        self.draw_scale = scale
        self.class_id, self.class_name, self.color = class_data

        self.background_color: QColor = QColor(Qt.black)
        self.set_draw_scale(scale)

        self.signal_holder = UAnnotationSignal()
        self._old_pos = self.pos()
        self._old_data = None

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

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            if value:
                self.setZValue(2)
            else:
                self.setZValue(1)
        return super().itemChange(change, value)

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

    def connect_selected_signal(self, func: Callable[[object], None]):
        self.signal_holder.select_event.connect(func)

    def disable_selection(self):
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)
        QApplication.restoreOverrideCursor()

    def enable_selection(self):
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self.setAcceptHoverEvents(True)
