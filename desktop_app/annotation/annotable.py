from typing import Optional
import math

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QMenu, QAction,
    QApplication, QMainWindow, QVBoxLayout, QComboBox, QPushButton, QWidget, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QTransform, QFont, QFontMetricsF, QCursor, QPixmap, QIcon, \
    QPainterPath, QImage
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal
from cv2 import Mat

from annotation.carousel import UThumbnailCarousel, UAnnotationThumbnail
from utility import FAnnotationData, FDetectAnnotationData, EAnnotationStatus
from utility import EWorkMode, FAnnotationClasses
from commander import UGlobalSignalHolder, UAnnotationSignalHolder


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
        print(self.draw_scale)

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
                self.class_name,
                QColor(self.color),
                int(self.parentItem().boundingRect().width()),
                int(self.parentItem().boundingRect().height())
            )
        except Exception as error:
            print(str(error))
            return None

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
        QApplication.restoreOverrideCursor()

    def boundingRect(self):
        rect = super().boundingRect()
        size = self.resize_handle_size / 2 * self.draw_scale
        if self.isSelected():
            return rect.adjusted(-size, -size, size, size)
        else:
            return rect

    def shape(self):
        if self.isSelected():
            path = QPainterPath()
            size = self.resize_handle_size / 2 * self.draw_scale
            rect = self.rect().adjusted(-size, -size, size, size)  # Расширяем границы
            path.addRect(rect)
            return path
        else:
            return super().shape()

    def paint(self, painter, option, widget=None):

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
                font = QFont("Arial", int(16 * self.draw_scale))
                font_color = QColor(Qt.black)

                font_metrics = QFontMetricsF(font)
                text_background_rect = font_metrics.boundingRect(text)
                text_background_rect.adjust(-6, -2, 12, 4)

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

                self.scene().update()

        else:
            painter.setBrush(QBrush(self.background_color))
            painter.setPen(QPen(self.color, int(self.line_width * self.draw_scale), Qt.SolidLine))
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
            scene = self.scene()
            if scene is not None:
                scene.clearSelection()
            self.setSelected(True)
            for name, handle in self.get_resize_handles().items():
                if handle.contains(event.pos()):
                    self.resizing = True
                    self.active_handle = name
                    break
            if self.resizing is False and self.rect().contains(event.pos()):
                super().mousePressEvent(event)
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
            if self.rect().contains(event.pos()):
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
    view_scale_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scale_factor = 1.0

        self.annotate_scene = QGraphicsScene()
        self.setScene(self.annotate_scene)

        self.annotate_start_point: Optional[QPointF] = None
        self.current_rect: Optional[UAnnotationBox] = None
        self.annotate_class: Optional[tuple[int, str, QColor]] = None
        self.work_mode = EWorkMode.DragMode

        self.current_image: Optional[QGraphicsPixmapItem] = None
        self.current_display_thumbnail: Optional[tuple[int, str, list[FAnnotationData]]] = None
        self.display_matrix: Optional[Mat] = None

        self.boxes_on_scene: list[UAnnotationBox] = list()

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        self.commander: Optional[UAnnotationSignalHolder] = None
        self.saved_work_mode = EWorkMode.DragMode

    def get_selectable_matrix(self):
        if self.current_display_thumbnail is None:
            return None, None
        else:
            t_id, *_ = self.current_display_thumbnail

            image = self.current_image.pixmap().toImage()
            image = image.convertToFormat(QImage.Format_RGB888)
            width, height = image.width(), image.height()
            buffer = image.bits()
            buffer.setsize(height * width * 3)
            matrix = np.array(buffer, dtype=np.uint8).reshape((height, width, 3))

            return t_id, matrix

    def set_commander(self, commander: UAnnotationSignalHolder):
        if commander:
            self.commander = commander
            # Привзяка событий
            self.commander.change_work_mode.connect(self.set_work_mode)
            self.commander.selected_thumbnail.connect(self.display_image)

    def display_image(self, thumbnail: tuple[int, str, list[FAnnotationData]]):
        self.annotate_scene.clear()
        self.boxes_on_scene.clear()
        if not thumbnail:
            self._clear_display_image()
            return

        self.current_display_thumbnail = thumbnail
        try:
            self.display_matrix = cv2.imread(self._get_current_thumb_image_path())
        except Exception as e:
            self._clear_display_image()
            print(f"Ошибка: {str(e)}")
            return

        try:
            image_t = cv2.cvtColor(self.display_matrix, cv2.COLOR_BGR2RGB)
            height, width, channel = image_t.shape
            bytes_per_line = 3 * width
            qimg = QImage(image_t.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
        except Exception as e:
            print(f"Ошибка: {str(e)}")
            self._clear_display_image()
            return

        self.current_image = QGraphicsPixmapItem(pixmap)
        self.annotate_scene.addItem(self.current_image)
        self.current_image.setPos(16000 - self.current_image.boundingRect().width() // 2,
                                  16000 - self.current_image.boundingRect().height() // 2)

        self._display_all_annotation()

        print("Количество боксов на сцене: ", len(self.boxes_on_scene))

    def _display_all_annotation(self):
        if self.current_display_thumbnail is None:
            return

        for item in self._get_current_thumb_annotation_data():
            data = item.get_data()
            if isinstance(item, FDetectAnnotationData):
                x, y, width, height = data
                ann_box = UAnnotationBox(
                    x,
                    y,
                    width,
                    height,
                    (item.get_id(), item.get_class_name(), item.get_color()),
                    1.0 / self.scale_factor,
                    self.current_image
                )
                self.view_scale_changed.connect(ann_box.set_draw_scale)
                self.boxes_on_scene.append(ann_box)
                self.scene().addItem(ann_box)
            else:
                continue


    def _clear_display_image(self):
        self.display_matrix = None
        self.current_display_thumbnail = None
        self.current_image = QPixmap(1920, 1400)
        self.current_image.fill(QColor(Qt.gray))
        self.annotate_scene.addItem(self.current_image)

    def handle_drag_start_event(self, key: int):
        if key == Qt.Key_Control:
            self.saved_work_mode = self.work_mode
            self.set_work_mode(EWorkMode.ForceDragMode.value)
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            for box in self.boxes_on_scene:
                box.disable_selection()

    def handle_drag_end_event(self, key: int):
        if key == Qt.Key_Control:
            self.setDragMode(QGraphicsView.NoDrag)
            self.set_work_mode(self.saved_work_mode.value)
            for box in self.boxes_on_scene:
                box.enable_selection()

    def wheelEvent(self, event):
        # Получаем текущее значение масштаба
        scale_change = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale_factor *= scale_change
        self.setTransform(QTransform().scale(self.scale_factor, self.scale_factor))
        self.view_scale_changed.emit(self.scale_factor)

    def add_annotation_box(self, x, y, width, height, class_data: tuple[int, str, QColor]):
        ann_box = UAnnotationBox(
            x,
            y,
            width,
            height,
            class_data,
            1.0 / self.scale_factor,
            self.current_image
        )

        if self.work_mode.value == EWorkMode.DragMode.value:
            ann_box.setAcceptedMouseButtons(Qt.AllButtons)
            ann_box.setAcceptHoverEvents(True)
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            ann_box.setAcceptedMouseButtons(Qt.NoButton)
            ann_box.setAcceptHoverEvents(False)

        self.view_scale_changed.connect(ann_box.set_draw_scale)

        if self.commander:
            self.commander.added_new_annotation.emit(self._get_current_thumb_index(), ann_box.get_annotation_data())
            print("Добавлен новый бокс под номером", len(self.boxes_on_scene), "данные бокса:", str(ann_box.get_annotation_data()))

        self.boxes_on_scene.append(ann_box)

        return ann_box

    def delete_on_press_key(self, key: int):
        if key == Qt.Key_Delete:
            items = self.annotate_scene.selectedItems()
            if len(items) <= 0:
                return
            selected_box = items[0]
            if isinstance(selected_box, UAnnotationBox):
                self.delete_annotation_box(selected_box)

    def delete_annotation_box(self, box: UAnnotationBox):
        if box in self.boxes_on_scene is False or self.current_display_thumbnail is None:
            return
        delete_index = self.boxes_on_scene.index(box)
        self.commander.deleted_annotation.emit(self._get_current_thumb_index(), delete_index)
        self.boxes_on_scene.remove(box)
        self.annotate_scene.removeItem(box)
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        if len(self.boxes_on_scene) == 0:
            self.commander.decrease_annotated_counter.emit()

        print("Удален бокс под номером", delete_index)

    def set_image_item(self, image):
        self.current_image = image

    def set_work_mode(self, mode: int):
        self.work_mode = EWorkMode(mode)
        print(self.work_mode.name)
        if self.work_mode.value == EWorkMode.AnnotateMode.value:
            self.annotate_scene.clearSelection()
            for box in self.boxes_on_scene:
                box.disable_selection()
        if self.work_mode.value == EWorkMode.DragMode.value:
            for box in self.boxes_on_scene:
                box.enable_selection()

    def set_annotate_class(self, class_id: int, class_name: str, color: QColor):
        # Изменение базового класса для разметки
        self.annotate_class = (class_id, class_name, QColor(color))

        # Если есть выбранный на сцене бокс разметки, то изменяем его класс
        selected = self.get_selected_annotation_box()
        if selected is None:
            return
        selected.update_annotate_class(self.annotate_class)
        data = selected.get_annotation_data()
        if self.commander is not None and self.current_display_thumbnail is not None:
            ann_index = self.boxes_on_scene.index(selected)
            self.commander.updated_annotation.emit(self._get_current_thumb_index(), ann_index, data)

    def get_selected_annotation_box(self):
        items = self.annotate_scene.selectedItems()
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
            if self.current_image is None or self.annotate_class is None:
                return super().mousePressEvent(event)
            if self.current_rect is None and self.annotate_start_point is None:
                cursor_pos = self.mapToScene(event.pos())
                self.annotate_start_point = self.current_image.mapFromScene(cursor_pos)
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
            current_cursor_pos = self.current_image.mapFromScene(self.mapToScene(event.pos()))
            rect = QRectF(self.annotate_start_point, current_cursor_pos).normalized()
            self.current_rect.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_display_thumbnail is None:
            return super().mouseReleaseEvent(event)
        if self.work_mode.value == EWorkMode.DragMode.value:
            selected = self.get_selected_annotation_box()
            if selected is None:
                pass
            else:
                index = self.boxes_on_scene.index(selected)
                data = selected.get_annotation_data()
                self.commander.updated_annotation.emit(
                    self._get_current_thumb_index(),
                    index,
                    data
                )
                print("Изменение бокса с номером", index, "и данными:" + str(data))
                pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.current_image is None or self.annotate_class is None:
                pass
            elif self.current_rect is not None and self.annotate_start_point is not None:
                if self.current_rect.get_square() < 25:
                    self.delete_annotation_box(self.current_rect)
                    return
                if self.commander is not None:
                    index = self.boxes_on_scene.index(self.current_rect)
                    data = self.current_rect.get_annotation_data()
                    self.current_rect.setSelected(True)
                    self.current_rect = None
                    self.annotate_start_point = None
                    self.commander.updated_annotation.emit(
                        self._get_current_thumb_index(),
                        index,
                        data
                    )
                    self.commander.change_work_mode.emit(EWorkMode.DragMode.value)

        super().mouseReleaseEvent(event)

    def _get_current_thumb_index(self):
        thumb_index, *_ = self.current_display_thumbnail
        return thumb_index

    def _get_current_thumb_image_path(self):
        _, image_path, _ = self.current_display_thumbnail
        return image_path

    def _get_current_thumb_annotation_data(self):
        *_, data = self.current_display_thumbnail
        return data

"""    def contextMenuEvent(self, event):
        if len(self.available_classes) == 0 or self.commander is None:
            return

        menu = QMenu()
        for class_d in self.available_classes:
            action = UAnnotationScene.set_action(
                menu,
                str(class_d),
                class_d.Color
            )
            action.triggered.connect(
                lambda checked=False, index=class_d.Cid: self.commander.changed_class_annotate.emit(index)
            )
            menu.addAction(action)

        menu.exec_(event.screenPos())"""


class UClassSelectorItem(QWidget):
    def __init__(self, class_id: int, name: str, color: QColor, parent=None):
        super().__init__(parent)
        self.class_id = class_id
        self.name = name
        self.color = color

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        self.color_label = QLabel(self)
        self.color_label.setFixedSize(20, 20)
        self.color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid transparent; border-radius: 2px;")

        self.text_label = QLabel(f"{class_id}: {name}", self)

        layout.addWidget(self.color_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        self.setLayout(layout)


class UClassSelectorList(QListWidget):
    class_selected = pyqtSignal(int, str, QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemClicked.connect(self.on_item_selected)

    def add_class(self, class_id: int, name: str, color: QColor):
        item = QListWidgetItem(self)
        widget = UClassSelectorItem(class_id, name, color)

        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

        item.setData(Qt.UserRole, (class_id, name, color))

    def on_item_selected(self, item: QListWidgetItem):
        class_id, name, color = item.data(Qt.UserRole)
        self.class_selected.emit(class_id, name, color)

