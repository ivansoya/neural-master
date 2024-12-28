from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem,
    QApplication, QMainWindow, QVBoxLayout, QComboBox, QPushButton, QWidget
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QTransform
from PyQt5.QtCore import Qt, QRectF, QPointF

from utility import EAnnotationMode, FClassRectStruct

class ResizableRect(QGraphicsRectItem):
    HANDLE_SIZE = 6

    def __init__(self, x, y, width, height, struct_type : FClassRectStruct):
        super().__init__(x, y, width, height)
        self.setFlags(
            QGraphicsRectItem.ItemIsSelectable |
            QGraphicsRectItem.ItemIsMovable
        )
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(Qt.red, 2))
        self.setBrush(QBrush(Qt.transparent))

        self.class_id = struct_type.Class_Id
        self.class_name = struct_type.Name
        self.color = struct_type.Color

        self.handles = []
        self.create_handles()

    def create_handles(self):
        """Создаем ручки для изменения размера."""
        positions = [
            QPointF(0, 0),                     # Верхний левый
            QPointF(self.rect().width(), 0),  # Верхний правый
            QPointF(0, self.rect().height()), # Нижний левый
            QPointF(self.rect().width(), self.rect().height())  # Нижний правый
        ]
        for pos in positions:
            handle = QGraphicsRectItem(
                QRectF(pos.x() - self.HANDLE_SIZE / 2, pos.y() - self.HANDLE_SIZE / 2, self.HANDLE_SIZE, self.HANDLE_SIZE),
                self
            )
            handle.setBrush(QBrush(QColor(0, 255, 0, 150)))  # Полупрозрачный зеленый
            handle.setPen(QPen(Qt.NoPen))
            handle.setFlag(QGraphicsRectItem.ItemIsMovable)
            self.handles.append(handle)

    def update_handles(self):
        """Обновление позиций ручек при изменении размера прямоугольника."""
        rect = self.rect()
        positions = [
            QPointF(rect.x(), rect.y()),                     # Верхний левый
            QPointF(rect.x() + rect.width(), rect.y()),      # Верхний правый
            QPointF(rect.x(), rect.y() + rect.height()),     # Нижний левый
            QPointF(rect.x() + rect.width(), rect.y() + rect.height())  # Нижний правый
        ]
        for i, pos in enumerate(positions):
            self.handles[i].setRect(
                QRectF(pos.x() - self.HANDLE_SIZE / 2, pos.y() - self.HANDLE_SIZE / 2, self.HANDLE_SIZE, self.HANDLE_SIZE)
            )

    def mouseMoveEvent(self, event):
        """Перемещение прямоугольника с обновлением ручек."""
        super().mouseMoveEvent(event)
        self.update_handles()

    def serialize(self):
        """Сериализация прямоугольника."""
        rect = self.rect()
        return {
            "id": self.class_id,
            "x": rect.x(),
            "y": rect.y(),
            "x2": rect.x() + rect.width(),
            "y2": rect.y() + rect.height()
        }

class UAnnotableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Установка начального масштаба
        self.scale_factor = 1.0

    def wheelEvent(self, event):
        # Получаем текущее значение масштаба
        scale_change = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale_factor *= scale_change
        self.setTransform(QTransform().scale(self.scale_factor, self.scale_factor))


class ImageAnnotationScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_point = None
        self.current_rect = None
        self.rect_draw_struct = None
        self.annotation_mode = EAnnotationMode.DragMode

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        self.image_item = None
        self.dragging_item = None
        self.last_mouse_position = None

    def mousePressEvent(self, event):
        if self.annotation_mode == EAnnotationMode.DragMode:
            pass
        elif self.annotation_mode == EAnnotationMode.AnnotateMode:
            if event.button() == Qt.LeftButton:
                self.start_point = event.scenePos()
                self.current_rect = ResizableRect(
                    self.start_point.x(), self.start_point.y(), 0, 0, self.rect_draw_struct
                )
                self.addItem(self.current_rect)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.annotation_mode == EAnnotationMode.DragMode:
            pass
        elif self.annotation_mode == EAnnotationMode.AnnotateMode:
            if self.start_point and self.current_rect:
                end_point = event.scenePos()
                rect = QRectF(self.start_point, end_point).normalized()
                self.current_rect.setRect(rect)
                self.current_rect.update_handles()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.annotation_mode == EAnnotationMode.DragMode:
            pass
        elif self.annotation_mode == EAnnotationMode.AnnotateMode:
            self.start_point = None
            self.current_rect = None
        super().mouseReleaseEvent(event)

    def setImageItem(self, image):
        self.image_item = image

    def setAnnotationMode(self, mode):
        self.annotation_mode = mode

    def setRectTypeDraw(self, rect_type):
        self.rect_draw_struct = rect_type