from typing import Optional

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QAction, QApplication,
    QVBoxLayout, QWidget, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtGui import QColor, QPainter, QTransform, QFont, QPixmap, QIcon, QImage
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, pyqtSlot, QPointF
from cv2 import Mat

from SAM2.sam2_net import USam2Net
from annotation.annotation_box import UAnnotationBox
from annotation.annotation_item import UAnnotationItem
from annotation.annotation_mask import UAnnotationMask
from annotation.annotation_polygon import UAnnotationPolygon
from annotation.modes.abstract import EWorkMode, UBaseAnnotationMode
from annotation.modes.sam2_annotate import USam2Annotation
from annotation.modes.segmentation import UMaskAnnotationMode
from annotation.modes.bounding_box import UBoxAnnotationMode
from annotation.modes.viewer import UViewerMode, UForceDragAnnotationMode

from utility import FAnnotationData, FDetectAnnotationData, EAnnotationStatus, FPolygonAnnotationData, UMessageBox
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
        self.sam2: Optional[USam2Net] = None

        self.annotate_mods: dict[EWorkMode, UBaseAnnotationMode] = dict()
        self.current_work_mode = EWorkMode.Viewer

        self.message_box: Optional[QMessageBox] = None

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

    def get_current_mode(self):
        return self.annotate_mods[self.current_work_mode]

    def set_scene_parameters(self, commander: UAnnotationSignalHolder, sam2: USam2Net):
        if commander:
            self.commander = commander
            # Привзяка событий
            self.commander.change_work_mode.connect(self.set_work_mode)
            self.commander.selected_thumbnail.connect(self.display_image)

            self.annotate_mods: dict[EWorkMode, UBaseAnnotationMode] = {
                EWorkMode.Viewer: UViewerMode(self, self.commander),
                EWorkMode.ForceDragMode: UForceDragAnnotationMode(self, self.commander),
                EWorkMode.BoxAnnotationMode: UBoxAnnotationMode(self, self.commander),
                EWorkMode.MaskAnnotationMode: UMaskAnnotationMode(self, self.commander),
                EWorkMode.SAM2: USam2Annotation(sam2, self, self.commander),
            }

    def display_image(self, thumbnail: tuple[int, str, list[FAnnotationData]], thumb_status: int):
        if self.check_work_done() is False:
            return

        self.annotate_mods[self.current_work_mode].refresh()
        self.annotate_scene.clear()
        self.annotation_items.clear()
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
                object_id, class_id, class_name, color, (x, y, width, height) = item.get_data()
                ann_box = self.add_annotation_box(
                    x,
                    y,
                    width,
                    height,
                    (class_id, class_name, QColor(color))
                )
                self.scene().addItem(ann_box)
                load_annotations.append((len(load_annotations), ann_box))
            elif isinstance(item, FPolygonAnnotationData):
                object_id, class_id, class_name, color, points_list = item.get_data()
                qt_points = [QPointF(x, y) for x, y in points_list]
                ann_mask = self.add_annotation_polygon(qt_points, (class_id, class_name, QColor(color)), True)
                self.scene().addItem(ann_mask)
                load_annotations.append((len(load_annotations), ann_mask))
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

    @pyqtSlot(int)
    def handle_on_key_press(self, key: int):
        self.annotate_mods[self.current_work_mode].on_key_press(key)

    @pyqtSlot(int)
    def handle_on_key_hold(self, key: int):
        self.annotate_mods[self.current_work_mode].on_key_hold(key)

    @pyqtSlot(int)
    def handle_on_key_release(self, key: int):
        self.annotate_mods[self.current_work_mode].on_key_release(key)

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
        self.annotate_mods[self.current_work_mode].on_wheel_mouse(self.scale_factor)

    def add_annotation_mask(self, polygons: list[UAnnotationPolygon], class_data: tuple[int, str, QColor], annotation_id: int):
        ann_mask = UAnnotationMask(
            polygons,
            class_data,
            self.scale_factor,
            annotation_id,
            self.current_image
        )

        self._set_annotation_item(ann_mask)
        self.scene().addItem(ann_mask)
        return ann_mask

    def add_annotation_polygon(self, points_list: list[QPointF], class_data: tuple[int, str, QColor], closed: bool = False):
        ann_mask = UAnnotationPolygon(
            points_list[:],
            class_data,
            self.scale_factor,
            closed,
            self.current_image
        )

        self._set_annotation_item(ann_mask)
        self.scene().addItem(ann_mask)
        return ann_mask

    def add_annotation_box(self, x, y, width, height, class_data: tuple[int, str, QColor]) -> UAnnotationBox:
        ann_box = UAnnotationBox(
            x,
            y,
            width,
            height,
            class_data,
            self.scale_factor,
            self.current_image
        )

        self._set_annotation_item(ann_box)
        self.scene().addItem(ann_box)
        return ann_box

    def _set_annotation_item(self, annotation_item: UAnnotationItem):
        if self.current_work_mode is EWorkMode.Viewer:
            annotation_item.change_activity_mode(True)
        else:
            annotation_item.change_activity_mode(False)

        annotation_item.connect_selected_signal(self.handle_on_select_annotation)
        annotation_item.connect_update_signal(self.handle_on_update_annotation)
        annotation_item.connect_delete_signal(self.handle_on_delete_annotation_item)

        self.annotation_items.append(annotation_item)

        return annotation_item

    def remake_box_to_mask(self, box: UAnnotationBox):
        if not box or box not in self.annotation_items:
            return

        mask_points = [
            QPointF(box.x(), box.y()),
            QPointF(box.x() + box.width(), box.y()),
            QPointF(box.x() + box.width(), box.y() + box.height()),
            QPointF(box.x(), box.y() + box.height()),
        ]

        index = self.annotation_items.index(box)
        if self.annotation_items[index].scene():
            self.annotation_items[index].scene().removeItem(self.annotation_items[index])

        self.annotation_items[index] = UAnnotationPolygon(
            mask_points,
            (box.get_class_id(), box.get_class_name(), box.get_color()),
            self.scale_factor,
            True,
            self.current_image
        )
        self._set_annotation_item(self.annotation_items[index])
        self.scene().addItem(self.annotation_items[index])
        self.annotation_items[index].setSelected(True)

        self.commander.updated_annotation.emit(
            self.get_current_thumb_index(),
            index,
            box.get_annotation_data(),
            self.annotation_items[index].get_annotation_data()
        )

    @pyqtSlot(object, bool)
    def handle_on_select_annotation(self, annotation: UAnnotationItem, to_select: bool):
        if not isinstance(annotation, UAnnotationItem):
            return

        try:
            selected_index = self.annotation_items.index(annotation)
            if self.commander:
                self.commander.selected_annotation.emit(selected_index, to_select)
        except Exception as error:
            print(str(error))

    @pyqtSlot(object, object, object)
    def handle_on_update_annotation(self, item: UAnnotationItem, prev_data: FAnnotationData, curr_data: FAnnotationData):
        index = self.annotation_items.index(item)
        self.commander.updated_annotation.emit(
            self.get_current_thumb_index(),
            index,
            prev_data,
            curr_data
        )

    @pyqtSlot(object)
    def handle_on_delete_annotation_item(self, annotation: UAnnotationItem | None):
        if not isinstance(annotation, UAnnotationItem) or annotation not in self.annotation_items or self.current_display_thumbnail is None:
            return

        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()

        if self.commander:
            deleted_data = annotation.get_annotation_data()
            deleted_index = self.annotation_items.index(annotation)
            self.commander.deleted_annotation.emit(self.get_current_thumb_index(), deleted_index, deleted_data)

        self.annotate_mods[self.current_work_mode].on_delete_item(annotation)

        if annotation.scene():
            self.annotate_scene.removeItem(annotation)

        if annotation.signal_holder:
            annotation.signal_holder.disconnect()
            annotation.signal_holder.deleteLater()

        self.annotation_items.remove(annotation)
        self.scene().update()

    def emit_commander_to_add(self, annotation_data: FAnnotationData):
        if self.commander:
            index, *_ = self.current_display_thumbnail
            self.commander.added_new_annotation.emit(index, annotation_data)

    def add_annotation_by_data(self, data: FAnnotationData):
        if isinstance(data, FDetectAnnotationData):
            object_id, class_id, class_name, color, (x, y, width, height) = data.get_data()
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

    def set_image_item(self, image):
        self.current_image = image

    def set_work_mode(self, mode: int):
        if mode == self.current_work_mode.value or self.check_work_done() is False:
            return

        new_work_mode = EWorkMode(mode)
        self.annotate_mods[self.current_work_mode].end_mode(new_work_mode)
        self.annotate_mods[new_work_mode].start_mode(self.current_work_mode)
        self.current_work_mode = new_work_mode

    def set_annotate_class(self, class_id: int, class_name: str, color: QColor):
        # Изменение базового класса для разметки
        self.annotate_class = (class_id, class_name, QColor(color))

        # Если есть выбранный на сцене бокс разметки, то изменяем его класс
        selected = self.get_selected_annotation()
        if selected is None:
            return
        prev_data = selected.get_annotation_data()
        selected.update_annotate_class(self.annotate_class)
        new_data = selected.get_annotation_data()
        if self.commander is not None and self.current_display_thumbnail is not None:
            ann_index = self.annotation_items.index(selected)
            self.commander.updated_annotation.emit(self.get_current_thumb_index(), ann_index, prev_data, new_data)

    def get_selected_annotation(self):
        items = self.annotate_scene.selectedItems()
        if len(items) == 0:
            return None
        selected = items[0]
        if isinstance(selected, UAnnotationItem):
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
            if annotation_item.scene():
                annotation_item.scene().removeItem(annotation_item)
            self.annotation_items.remove(annotation_item)

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
        if self.annotate_mods[self.current_work_mode].on_press_mouse(event):
            return
        else:
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

    def check_work_done(self):
        if self.annotate_mods[self.current_work_mode].is_work_done():
            return True

        if self.message_box is None:
            self.message_box = QMessageBox()
            self.message_box.setIcon(QMessageBox.Warning)
            self.message_box.setWindowTitle("Предупреждение!")
            self.message_box.setText("Завершите работу!")
            self.message_box.setStandardButtons(QMessageBox.Ok)
            self.message_box.show()
            self.message_box.finished.connect(lambda _: setattr(self, 'message_box', None))
        return False

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