from typing import Optional
import math

from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QMenu, QAction,
    QApplication, QMainWindow, QVBoxLayout, QComboBox, QPushButton, QWidget
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QTransform, QFont, QFontMetricsF, QCursor, QPixmap, QIcon
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal

from utility import FAnnotationData
from utility import EWorkMode, FClassData
from commander import UGlobalSignalHolder

class UAnnotationBox(QGraphicsRectItem):
    update_event = pyqtSignal(object, object)

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
            class_data: FClassData,
            parent = None
    ):
        super().__init__(parent)

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable
        )

        self.setAcceptHoverEvents(True)

        self.isActive = True

        self.setRect(x1, y1, width, height)

        self.color = class_data.Color
        self.class_id = class_data.Cid
        self.class_name = class_data.Name

        self.line_width = 4
        self.draw_scale = 1

        #self.setPen(QPen(self.color, self.line_width, Qt.SolidLine))

        self.background_color = QColor(class_data.Color)
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
            'top_line': QRectF(rect.topLeft() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(rect.width() + line_width, line_width)),
            'right_line': QRectF(rect.topRight() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(line_width, rect.height() + line_width)),
            'bottom_line': QRectF(rect.bottomLeft() - QPointF(line_width / 2, line_width / 2),
                               QSizeF(rect.width() + line_width, line_width)),
            'left_line': QRectF(rect.topLeft() - QPointF(line_width/ 2, line_width / 2),
                               QSizeF(line_width, rect.height() + line_width)),
        }

    @staticmethod
    def get_resize_cursor(active_handle : str):
        if active_handle in UAnnotationBox.resize_cursors:
            return UAnnotationBox.resize_cursors[active_handle]
        else:
            return 'default'

    def update_annotate_class(self, class_data: FClassData):
        self.color = class_data.Color
        self.class_id = class_data.Cid
        self.class_name = class_data.Name

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
        #super().paint(painter, option, widget)

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

                # Фон
                painter.setBrush(QBrush(self.color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(text_background_rect)

                # Текст
                painter.setFont(font)
                painter.setPen(font_color)
                painter.drawText(text_background_rect, Qt.AlignCenter, text)

        else:
            painter.setBrush(QBrush(self.background_color))
            painter.setPen(QPen(self.color, self.line_width * self.draw_scale, Qt.SolidLine))
            painter.drawRect(self.boundingRect())

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedChange:
            if value:
                self.setZValue(2)
            else:
                self.setZValue(1)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for name, handle in self.get_resize_handles().items():
                if handle.contains(event.pos()):
                    self.resizing = True
                    self.active_handle = name
                    break
            scene = self.scene()
            if scene is not None:
                scene.clearSelection()
            self.setSelected(True)
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

class UAnnotationGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scale_factor = 1.0

    def enable_drag_mode(self, key: int):
        if key == Qt.Key_Control:
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def disable_drag_mode(self, key: int):
        if key == Qt.Key_Control:
            self.setDragMode(QGraphicsView.NoDrag)

    def wheelEvent(self, event):
        # Получаем текущее значение масштаба
        scale_change = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale_factor *= scale_change
        self.setTransform(QTransform().scale(self.scale_factor, self.scale_factor))


class ImageAnnotationScene(QGraphicsScene):
    def __init__(self, commander: UGlobalSignalHolder = None, parent=None):
        super().__init__(parent)
        self.annotate_start_point : Optional[QPointF] = None
        self.current_rect : Optional[UAnnotationBox] = None
        self.annotate_class : Optional[FClassData] = None
        self.work_mode = EWorkMode.DragMode

        self.commander = commander

        self.image : Optional[QGraphicsPixmapItem] = None

        self.boxes_on_scene : list[UAnnotationBox] = list()
        self.available_classes: list[FClassData] = list()

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        if self.commander is not None:
            self.commander.change_work_mode.connect(self.set_work_mode)
            self.commander.changed_class_annotate.connect(self.set_annotate_class)


    def add_annotation_box(self, x, y, width, height, class_data: FClassData, do_emit: bool = True):
        ann_box = UAnnotationBox(
            x,
            y,
            width,
            height,
            class_data,
            self.image
        )

        if self.work_mode.value == EWorkMode.DragMode.value:
            ann_box.setAcceptedMouseButtons(Qt.AllButtons)
            ann_box.setAcceptHoverEvents(True)
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            ann_box.setAcceptedMouseButtons(Qt.NoButton)
            ann_box.setAcceptHoverEvents(False)

        if self.commander:
            self.commander.ctrl_pressed.connect(ann_box.on_ctrl_pressed)
            self.commander.ctrl_released.connect(ann_box.on_ctrl_release)

            data = FAnnotationData(x, y, width, height, class_data.Cid,
                                   res_w=self.image.boundingRect().width(),
                                   res_h=self.image.boundingRect().height()
                                   )
            if do_emit is True:
                self.commander.added_new_annotation.emit(data)
            print("Добавлен новый бокс под номером", len(self.boxes_on_scene), "данные бокса:", str(data))

        self.boxes_on_scene.append(ann_box)

        return ann_box

    def delete_on_press_key(self, key: int):
        if key == Qt.Key_Delete:
            items = self.selectedItems()
            if len(items) <= 0:
                return
            selected_box = items[0]
            if isinstance(selected_box, UAnnotationBox):
                self.delete_annotation_box(selected_box)

    def delete_annotation_box(self, box: UAnnotationBox):
        if box in self.boxes_on_scene is False:
            return
        delete_index = self.boxes_on_scene.index(box)
        self.commander.deleted_annotation.emit(
            delete_index
        )
        self.boxes_on_scene.remove(box)
        self.removeItem(box)

        if len(self.boxes_on_scene) == 0:
            self.commander.decrease_annotated_counter.emit()

        print("Удален бокс под номером", delete_index)

    def set_image_item(self, image):
        self.image = image

    def set_work_mode(self, mode: int):
        self.work_mode = EWorkMode(mode)
        print(self.work_mode.name)
        if self.work_mode.value == EWorkMode.AnnotateMode.value:
            self.clearSelection()
            for box in self.boxes_on_scene:
                box.disable_selection()
        if self.work_mode.value == EWorkMode.DragMode.value:
            for box in self.boxes_on_scene:
                box.enable_selection()

    def set_annotate_class(self, index: int):
        # Изменение базового класса для разметки
        if index < 0 or index >= len(self.available_classes):
            return
        self.annotate_class = self.available_classes[index]

        # Если есть выбранный на сцене бокс разметки, то изменяем его класс
        selected = self.get_selected_annotation_box()
        if selected is None:
            return
        selected.update_annotate_class(self.annotate_class)
        data = FAnnotationData(
            selected.x(),
            selected.y(),
            selected.width(),
            selected.height(),
            selected.class_id,
            res_w=self.image.boundingRect().width(),
            res_h=self.image.boundingRect().height()
        )
        if self.commander is not None:
            ann_index = self.boxes_on_scene.index(selected)
            self.commander.updated_annotation.emit(ann_index, data)


    def add_class(self, class_data: FClassData):
        self.available_classes.append(class_data)

    def set_classes_list(self, class_list: list[FClassData]):
        self.available_classes = class_list

    def get_selected_annotation_box(self):
        items = self.selectedItems()
        if len(items) == 0:
            return None
        selected = items[0]
        if isinstance(selected, UAnnotationBox):
            return selected
        else:
            return None

    def clean_all_annotations(self, key: int):
        for i in range(len(self.boxes_on_scene) - 1, -1, -1):
            self.delete_annotation_box(self.boxes_on_scene[i])

    @staticmethod
    def set_action(menu, text, color: QColor):
        pixmap = QPixmap(40, 20)
        pixmap.fill(color)
        return QAction(QIcon(pixmap), text, menu)

    def clear(self):
        for box in self.boxes_on_scene:
            self.removeItem(box)
        self.boxes_on_scene.clear()
        super().clear()

    def mousePressEvent(self, event):
        if self.work_mode.value == EWorkMode.DragMode.value:
            pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.image is None or self.annotate_class is None:
                return super().mousePressEvent(event)
            if self.current_rect is None and self.annotate_start_point is None:
                cursor_pos = event.scenePos()
                self.annotate_start_point = self.image.mapFromScene(cursor_pos)
                self.current_rect = self.add_annotation_box(
                    self.annotate_start_point.x(),
                    self.annotate_start_point.y(),
                    1,
                    1,
                    self.annotate_class,
                )
            elif self.current_rect is not None and self.annotate_start_point is not None:
                print(self.current_rect.rect())
                self.current_rect = None
                self.annotate_start_point = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.work_mode.value == EWorkMode.DragMode.value:
            pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.current_rect is None or self.annotate_start_point is None:
                return super().mouseMoveEvent(event)
            current_cursor_pos = self.image.mapFromScene(event.scenePos())
            rect = QRectF(self.annotate_start_point, current_cursor_pos).normalized()
            self.current_rect.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.work_mode.value == EWorkMode.DragMode.value:
            selected = self.get_selected_annotation_box()
            if selected is None:
                pass
            else:
                index = self.boxes_on_scene.index(selected)
                data = FAnnotationData(
                        selected.x(),
                        selected.y(),
                        selected.width(),
                        selected.height(),
                        selected.class_id,
                        res_w=self.image.boundingRect().width(),
                        res_h=self.image.boundingRect().height()
                    )
                self.commander.updated_annotation.emit(
                    index,
                    data
                )
                print("Изменение бокса с номером", index, "и данными:" + str(data))
                pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.image is None or self.annotate_class is None:
                pass
            elif self.current_rect is not None and self.annotate_start_point is not None:
                if self.current_rect.get_square() < 25:
                    self.delete_annotation_box(self.current_rect)
                    return
                if self.commander is not None:
                    index = self.boxes_on_scene.index(self.current_rect)
                    data = FAnnotationData(
                        self.current_rect.x(),
                        self.current_rect.y(),
                        self.current_rect.width(),
                        self.current_rect.height(),
                        self.current_rect.class_id,
                        res_w=self.image.boundingRect().width(),
                        res_h=self.image.boundingRect().height()
                    )
                    self.current_rect.setSelected(True)
                    self.current_rect = None
                    self.annotate_start_point = None
                    self.commander.updated_annotation.emit(
                        index,
                        data
                    )
                    self.commander.change_work_mode.emit(EWorkMode.DragMode.value)

        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if len(self.available_classes) == 0 or self.commander is None:
            return

        menu = QMenu()
        for class_d in self.available_classes:
            action = ImageAnnotationScene.set_action(
                menu,
                str(class_d),
                FClassData.get_save_color(class_d.Cid)
            )
            action.triggered.connect(
                lambda checked=False, index=class_d.Cid: self.commander.changed_class_annotate.emit(index)
            )
            menu.addAction(action)

        menu.exec_(event.screenPos())