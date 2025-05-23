from typing import Optional

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QAction, QApplication,
    QVBoxLayout, QWidget, QHBoxLayout, QLabel, QListWidget, QListWidgetItem
)
from PyQt5.QtGui import QColor, QPainter, QTransform, QFont, QPixmap, QIcon, QImage
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, pyqtSlot
from cv2 import Mat

from annotation.annotation_box import UAnnotationBox
from annotation.annotation_item import UAnnotationItem
from annotation.annotation_mode import EWorkMode, UDragAnnotationMode, UForceDragAnnotationMode, UBoxAnnotationMode, \
    UBaseAnnotationMode

from utility import FAnnotationData, FDetectAnnotationData, EAnnotationStatus
from commander import UAnnotationSignalHolder

class UAnnotationGraphicsView(QGraphicsView):
    view_scale_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scale_factor = 1.0
        self.is_model_annotating = False

        self.annotate_scene = QGraphicsScene()
        self.setScene(self.annotate_scene)

        self.annotate_class: Optional[tuple[int, str, QColor]] = None

        self.current_image: Optional[QGraphicsPixmapItem] = None
        self.current_display_thumbnail: Optional[tuple[int, str, list[FAnnotationData]]] = None
        self.display_matrix: Optional[Mat] = None

        self.annotation_items: list[UAnnotationItem] = list()

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        self.overlay: Optional[UAnnotationOverlayWidget] = None

        self.commander: Optional[UAnnotationSignalHolder] = None

        self.annotate_mods: dict[EWorkMode, UBaseAnnotationMode] = dict()
        self.current_work_mode = EWorkMode.DragMode

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

            self.annotate_mods: dict[EWorkMode, UBaseAnnotationMode] = {
                EWorkMode.DragMode: UDragAnnotationMode(self, self.commander),
                EWorkMode.ForceDragMode: UForceDragAnnotationMode(self, self.commander),
                EWorkMode.BoxAnnotationMode: UBoxAnnotationMode(self, self.commander)
            }

    def display_image(self, thumbnail: tuple[int, str, list[FAnnotationData]], thumb_status: int):
        self.annotate_scene.clear()
        self.annotation_items.clear()
        self.annotate_mods[self.current_work_mode].refresh()
        if not thumbnail:
            self._clear_display_image()
            return

        self.current_display_thumbnail = thumbnail
        image_path = self._get_current_thumb_image_path()
        try:
            self.display_matrix = cv2.imread(image_path)
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
        self.is_model_annotating = True if thumb_status == EAnnotationStatus.PerformingAnnotation.value else False
        if self.is_model_annotating and self.overlay is None:
            self.overlay = UAnnotationOverlayWidget(self)
            self.raise_()
        elif not self.is_model_annotating and self.overlay:
            self.overlay = UAnnotationOverlayWidget.delete_overlay(self.overlay)
        if self.commander:
            self.commander.displayed_image.emit(image_path)
        self.update()

    def _display_all_annotation(self):
        if self.current_display_thumbnail is None:
            return

        load_annotations: list[tuple] = list()
        for item in self._get_current_thumb_annotation_data():
            if isinstance(item, FDetectAnnotationData):
                class_id, class_name, color, (x, y, width, height) = item.get_data()
                ann_box = self.add_annotation_box(
                    x,
                    y,
                    width,
                    height,
                    (class_id, class_name, QColor(color))
                )
                self.scene().addItem(ann_box)
                load_annotations.append((len(load_annotations), ann_box))
            else:
                continue
        if self.commander:
            self.commander.display_annotations.emit(load_annotations)

    def _clear_display_image(self):
        self.display_matrix = None
        self.current_display_thumbnail = None
        self.current_image = QPixmap(1920, 1400)
        self.current_image.fill(QColor(Qt.gray))
        self.annotate_scene.addItem(self.current_image)

    def handle_drag_start_event(self, key: int):
        if key == Qt.Key_Control:
            self.set_work_mode(EWorkMode.ForceDragMode.value)

    def handle_drag_end_event(self, key: int):
        if key == Qt.Key_Control:
            prev_mode = self.annotate_mods[self.current_work_mode].get_previous_mode()
            if prev_mode: self.set_work_mode(prev_mode.value)

    @pyqtSlot(int)
    def handle_image_move_to_model(self, index: int):
        current_index = self.get_current_thumb_index()
        if index == current_index:
            self.is_model_annotating = True
            if self.overlay is None:
                self.overlay = UAnnotationOverlayWidget(self)
                self.overlay.raise_()

    def handle_get_result_from_model(self, ann_list: list[FAnnotationData]):
        for item in self.annotate_scene.items():
            if item == self.current_image:
                continue
            else:
                self.annotate_scene.removeItem(item)
        self.annotation_items.clear()
        for annotation in ann_list:
            self.add_annotation_by_data(annotation)
        self.is_model_annotating = False
        self.overlay = UAnnotationOverlayWidget.delete_overlay(self.overlay)
        self.update()

    def wheelEvent(self, event):
        # Получаем текущее значение масштаба
        scale_change = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale_factor *= scale_change
        self.setTransform(QTransform().scale(self.scale_factor, self.scale_factor))
        for item in self.annotation_items:
            item.set_draw_scale(self.scale_factor)

    def add_annotation_box(self, x, y, width, height, class_data: tuple[int, str, QColor]):
        ann_box = UAnnotationBox(
            x,
            y,
            width,
            height,
            class_data,
            self.scale_factor,
            self.current_image
        )

        if self.current_work_mode is EWorkMode.DragMode:
            ann_box.setAcceptedMouseButtons(Qt.AllButtons)
            ann_box.setAcceptHoverEvents(True)
        elif self.current_work_mode is EWorkMode.BoxAnnotationMode:
            ann_box.setAcceptedMouseButtons(Qt.NoButton)
            ann_box.setAcceptHoverEvents(False)

        #self.view_scale_changed.connect(ann_box.set_draw_scale)
        ann_box.connect_selected_signal(self.handle_on_select_annotation)

        self.annotation_items.append(ann_box)

        return ann_box

    @pyqtSlot(object)
    def handle_on_select_annotation(self, annotation_item: object):
        if isinstance(annotation_item, UAnnotationItem):
            try:
                index = self.annotation_items.index(annotation_item)
                if self.commander:
                    self.commander.selected_annotation.emit(index)
            except Exception as error:
                print(str(error))

    def emit_commander_to_add(self, annotation_data: FAnnotationData):
        if self.commander:
            index, *_ = self.current_display_thumbnail
            self.commander.added_new_annotation.emit(index, annotation_data)

    def add_annotation_by_data(self, data: FAnnotationData):
        if isinstance(data, FDetectAnnotationData):
            class_id, class_name, color, (x, y, width, height) = data.get_data()
            annotation_box = self.add_annotation_box(
                x,
                y,
                width,
                height,
                (class_id, class_name, QColor(color))
            )
            #self._emit_commander_on_add(annotation_box)
        else:
            return

    def center_on_selected(self):
        if not self.current_image:
            return
        self.fitInView(self.current_image.sceneBoundingRect(), Qt.KeepAspectRatio)

        self.scale_factor = self.transform().m11()
        for item in self.annotation_items:
            item.set_draw_scale(self.scale_factor)

    def delete_on_press_key(self, key: int):
        if key == Qt.Key_Delete:
            items = self.annotate_scene.selectedItems()
            if len(items) <= 0:
                return
            selected_annotation = items[0]
            if isinstance(selected_annotation, UAnnotationBox):
                try:
                    index = self.annotation_items.index(selected_annotation)
                except Exception as error:
                    print(str(error))
                    return
                deleted_data = selected_annotation.get_annotation_data()
                self.delete_annotation_item(selected_annotation)
                if self.commander:
                    self.commander.deleted_annotation.emit(self.get_current_thumb_index(), index, deleted_data)

    def delete_annotation_item(self, annotation: UAnnotationItem):
        if annotation in self.annotation_items is False or self.current_display_thumbnail is None:
            return

        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        if annotation.signal_holder:
            annotation.signal_holder.disconnect()
            annotation.signal_holder.deleteLater()
        self.annotation_items.remove(annotation)
        if annotation.scene() is not None:
            self.annotate_scene.removeItem(annotation)
        annotation.setParentItem(None)

    def set_image_item(self, image):
        self.current_image = image

    def set_work_mode(self, mode: int):
        new_work_mode = EWorkMode(mode)
        self.annotate_mods[self.current_work_mode].end_mode(new_work_mode)
        self.annotate_mods[new_work_mode].start_mode(self.current_work_mode)
        self.current_work_mode = new_work_mode

    def set_annotate_class(self, class_id: int, class_name: str, color: QColor):
        # Изменение базового класса для разметки
        self.annotate_class = (class_id, class_name, QColor(color))

        # Если есть выбранный на сцене бокс разметки, то изменяем его класс
        selected = self.get_selected_annotation_box()
        if selected is None:
            return
        prev_data = selected.get_annotation_data()
        selected.update_annotate_class(self.annotate_class)
        new_data = selected.get_annotation_data()
        if self.commander is not None and self.current_display_thumbnail is not None:
            ann_index = self.annotation_items.index(selected)
            self.commander.updated_annotation.emit(self.get_current_thumb_index(), ann_index, prev_data, new_data)

    def get_selected_annotation_box(self):
        items = self.annotate_scene.selectedItems()
        if len(items) == 0:
            return None
        selected = items[0]
        if isinstance(selected, UAnnotationBox):
            return selected
        else:
            return None

    def select_annotation_by_index(self, index: int):
        if 0 <= index < len(self.annotation_items):
            self.scene().clearSelection()
            self.annotation_items[index].setSelected(True)

    def clean_all_annotations(self, to_emit: bool = False):
        self.scene().clearSelection()
        while self.annotation_items:
            annotation_item = self.annotation_items[-1]

            deleted_data = annotation_item.get_annotation_data()
            self.delete_annotation_item(annotation_item)

            if to_emit:
                self.commander.deleted_annotation.emit(
                    self.get_current_thumb_index(),
                    len(self.annotation_items),
                    deleted_data
                )

    @staticmethod
    def set_action(menu, text, color: QColor):
        pixmap = QPixmap(40, 20)
        pixmap.fill(color)
        return QAction(QIcon(pixmap), text, menu)

    def clear(self):
        self.scene().clear()
        self.current_image = None
        self.annotation_items.clear()

    def mousePressEvent(self, event):
        if self.is_model_annotating:
            return
        self.annotate_mods[self.current_work_mode].on_press_mouse(event)

        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_model_annotating:
            return
        self.annotate_mods[self.current_work_mode].on_move_mouse(event)

        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_model_annotating:
            return
        self.annotate_mods[self.current_work_mode].on_release_mouse(event)

        return super().mouseReleaseEvent(event)

    def get_current_thumb_index(self) -> int:
        thumb_index, *_ = self.current_display_thumbnail
        return thumb_index

    def get_annotations(self):
        return self.annotation_items

    def get_image(self):
        return self.current_image

    def get_current_class(self):
        return self.annotate_class

    def _get_current_thumb_image_path(self):
        _, image_path, _ = self.current_display_thumbnail
        return image_path

    def _get_current_thumb_annotation_data(self):
        *_, data = self.current_display_thumbnail
        return data

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay:
            self.overlay.setGeometry(self.rect())


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


class UAnnotationOverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label = QLabel("Идет разметка", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Arial", 24, QFont.Bold))
        self.label.setStyleSheet("color: white;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.setGeometry(self.parent().rect())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

    def resizeEvent(self, event):
        self.label.setFixedSize(self.size())  # Делаем текст на весь экран

    @staticmethod
    def delete_overlay(overlay: 'UAnnotationOverlayWidget'):
        if overlay:
            overlay.hide()
            overlay.deleteLater()
            return None
        return overlay