from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPixmapItem,
    QApplication, QMainWindow, QVBoxLayout, QComboBox, QPushButton, QWidget
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QTransform, QFont, QFontMetricsF, QCursor
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF

from utility import EWorkMode, FClassData

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

    def __init__(self, x1: float, y1: float, x2: float, y2:float, class_data: FClassData, parent = None):
        super().__init__(parent)

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable
        )

        self.setAcceptHoverEvents(True)

        self.setRect(x1, y1, x2 - x1, y2 - y1)
        self.cords = QPointF()

        self.color = class_data.Color
        self.class_id = class_data.Cid
        self.class_name = class_data.Name

        self.line_width = 4

        self.setPen(QPen(self.color, self.line_width, Qt.SolidLine))
        self.pen().setCosmetic(True)
        self.background_color = QColor(class_data.Color)
        self.background_color.setAlpha(50)
        self.setBrush(QBrush(self.background_color))

        self.resizing = False
        self.resize_handle_size = 12
        self.active_handle = None

        self.update_box_cords()

    def update_box_cords(self):
        self.cords = self.pos() + self.rect().topLeft()

    def hoverMoveEvent(self, event):
        for name, handle in self.get_resize_handles().items():
            if handle.contains(event.pos()):
                cursor = UAnnotationBox.get_resize_cursor(name)
                if QApplication.overrideCursor() is QCursor(cursor):
                    pass
                else:
                    QApplication.restoreOverrideCursor()
                    QApplication.setOverrideCursor(QCursor(cursor))
                super().hoverMoveEvent(event)
                return

        if QApplication.overrideCursor() is not QCursor(Qt.SizeAllCursor):
            QApplication.restoreOverrideCursor()
            QApplication.setOverrideCursor(QCursor(Qt.SizeAllCursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        QApplication.restoreOverrideCursor()
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        if self.isSelected():
            # Удаление фона
            self.setBrush(QBrush(Qt.transparent))
            # Отрисовка якорей
            handles = self.get_resize_handles()
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)

            for handle in handles.values():
                painter.drawRect(handle)

            if self.resizing is False:
                # Отрисовка текста на фоне
                text = f"ID: {self.class_id}, {self.class_name}"
                font = QFont("Arial", 16)
                font_color = QColor(Qt.black)

                font_metrics = QFontMetricsF(font)
                text_background_rect = font_metrics.boundingRect(text)
                text_background_rect.adjust(15, 2, 15, 2)

                # Изменение начала координат для фона
                top_left = self.get_resize_handles()['top_left']
                text_background_rect.moveTo(top_left.x(), top_left.y() - text_background_rect.height() - 2)

                #Фон
                painter.setBrush(QBrush(self.color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(text_background_rect)

                # Текст
                painter.setFont(font)
                painter.setPen(font_color)
                painter.drawText(text_background_rect, Qt.AlignCenter, text)

        else:
            self.setBrush(QBrush(self.background_color))

    @staticmethod
    def get_resize_cursor(active_handle : str):
        if active_handle in UAnnotationBox.resize_cursors:
            return UAnnotationBox.resize_cursors[active_handle]
        else:
            return 'default'

    def correct_rect(self):
        rect = self.rect()
        if rect.top() > rect.bottom():
            rect = QRectF(rect.left(), rect.bottom(), rect.width(), -rect.height())
        if rect.left() > rect.right():
            rect = QRectF(rect.right(), rect.top(), -rect.width(), rect.height())

        self.setRect(rect)

    def get_resize_handles(self):
        rect = self.rect()
        handle_size = self.resize_handle_size
        return {
            'top_left': QRectF(rect.topLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_right': QRectF(rect.topRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_left': QRectF(rect.bottomLeft() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'bottom_right': QRectF(rect.bottomRight() - QPointF(handle_size / 2, handle_size / 2),
                               QSizeF(handle_size, handle_size)),
            'top_line': QRectF(rect.topLeft() - QPointF(self.line_width / 2, self.line_width / 2),
                               QSizeF(rect.width() + self.line_width, self.line_width)),
            'right_line': QRectF(rect.topRight() - QPointF(self.line_width / 2, self.line_width / 2),
                               QSizeF(self.line_width, rect.height() + self.line_width)),
            'bottom_line': QRectF(rect.bottomLeft() - QPointF(self.line_width / 2, self.line_width / 2),
                               QSizeF(rect.width() + self.line_width, self.line_width)),
            'left_line': QRectF(rect.topLeft() - QPointF(self.line_width / 2, self.line_width / 2),
                               QSizeF(self.line_width, rect.height() + self.line_width)),
        }

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for name, handle in self.get_resize_handles().items():
                if handle.contains(event.pos()):
                    self.resizing = True
                    self.active_handle = name
                    break
        else:
            super().mousePressEvent(event)

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
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.active_handle = None
            self.correct_rect()
            self.update()
        else:
            super().mouseReleaseEvent(event)

        self.update_box_cords()
        print(self.cords)


class UAnnotableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        #self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scale_factor = 1.0

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.setDragMode(QGraphicsView.NoDrag)
        super().keyReleaseEvent(event)

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
        self.work_mode = EWorkMode.DragMode

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        self.image_item = None
        self.dragging_item = None
        self.last_mouse_position = None

    def mousePressEvent(self, event):
        if self.work_mode == EWorkMode.DragMode:
            pass
        elif self.work_mode == EWorkMode.AnnotateMode:
            if self.image_item is None:
                pass
            if event.button() == Qt.LeftButton:
                self.start_point = event.scenePos()
                self.current_rect = UAnnotationBox(
                    self.start_point.x(), self.start_point.y(), 0, 0, self.rect_draw_struct
                )
                self.addItem(self.current_rect)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.work_mode == EWorkMode.DragMode:
            pass
        elif self.work_mode == EWorkMode.AnnotateMode:
            if self.image_item is None:
                pass
            if self.start_point and self.current_rect:
                end_point = event.scenePos()
                rect = QRectF(self.start_point, end_point).normalized()
                self.current_rect.setRect(rect)
                self.current_rect.update_handles()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.work_mode == EWorkMode.DragMode:
            pass
        elif self.work_mode == EWorkMode.AnnotateMode:
            if self.image_item is None:
                pass
            self.start_point = None
            self.current_rect = None
        super().mouseReleaseEvent(event)

    def setImageItem(self, image):
        self.image_item = image

    def setAnnotationMode(self, mode):
        self.work_mode = mode

    def setRectTypeDraw(self, rect_type):
        self.rect_draw_struct = rect_type