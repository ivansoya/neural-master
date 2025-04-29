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
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal, pyqtSlot
from click import command
from cv2 import Mat

from annotation.annotation_box import UAnnotationBox
from annotation.carousel import UThumbnailCarousel, UAnnotationThumbnail
from utility import FAnnotationData, FDetectAnnotationData, EAnnotationStatus
from utility import EWorkMode, FAnnotationClasses
from commander import UGlobalSignalHolder, UAnnotationSignalHolder

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

        self.annotate_start_point: Optional[QPointF] = None
        self.current_rect: Optional[UAnnotationBox] = None
        self.annotate_class: Optional[tuple[int, str, QColor]] = None
        self.work_mode = EWorkMode.DragMode

        self.current_image: Optional[QGraphicsPixmapItem] = None
        self.current_display_thumbnail: Optional[tuple[int, str, list[FAnnotationData]]] = None
        self.display_matrix: Optional[Mat] = None

        self.boxes_on_scene: list[UAnnotationBox] = list()

        self.setSceneRect(QRectF(0, 0, 32000, 32000))  # Устанавливаем размер сцены (ширина, высота)

        self.overlay: Optional[UAnnotationOverlayWidget] = None

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

    def display_image(self, thumbnail: tuple[int, str, list[FAnnotationData]], thumb_status: int):
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
        self.is_model_annotating = True if thumb_status == EAnnotationStatus.PerformingAnnotation.value else False
        if self.is_model_annotating and self.overlay is None:
            self.overlay = UAnnotationOverlayWidget(self)
            self.raise_()
        elif not self.is_model_annotating and self.overlay:
            self.overlay = UAnnotationOverlayWidget.delete_overlay(self.overlay)
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
                """
                class_id, class_name, color, (x, y, width, height) = item.get_data()
                ann_box = UAnnotationBox(
                    x,
                    y,
                    width,
                    height,
                    (class_id, class_name, QColor(color)),
                    self.scale_factor,
                    self.current_image
                )
                self.view_scale_changed.connect(ann_box.set_draw_scale)
                self.boxes_on_scene.append(ann_box)
                """
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

    @pyqtSlot(int)
    def handle_image_move_to_model(self, index: int):
        current_index = self.get_current_thumb_index()
        if index == current_index:
            self.is_model_annotating = True
            if self.overlay is None:
                self.overlay = UAnnotationOverlayWidget(self)
                self.overlay.raise_()

    def handle_get_result_from_model(self, ann_list: list[FAnnotationData]):
        print("Переход в функцию annotation_scene.handle_get_result_from_model")
        self.display_image(
            self.current_display_thumbnail,
            EAnnotationStatus.Annotated.value if len(ann_list) > 0 else EAnnotationStatus.MarkedDrop.value
        )
        for annotation in ann_list:
            self.add_annotation_by_data(annotation)
        self.is_model_annotating = False
        self.overlay = UAnnotationOverlayWidget.delete_overlay(self.overlay)
        self.update()
        print("Выход и функции annotation_scene.handle_get_result_from_model")

    def wheelEvent(self, event):
        # Получаем текущее значение масштаба
        scale_change = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale_factor *= scale_change
        self.setTransform(QTransform().scale(self.scale_factor, self.scale_factor))
        for box in self.boxes_on_scene:
            box.set_draw_scale(self.scale_factor)

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

        if self.work_mode.value == EWorkMode.DragMode.value:
            ann_box.setAcceptedMouseButtons(Qt.AllButtons)
            ann_box.setAcceptHoverEvents(True)
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            ann_box.setAcceptedMouseButtons(Qt.NoButton)
            ann_box.setAcceptHoverEvents(False)

        #self.view_scale_changed.connect(ann_box.set_draw_scale)
        ann_box.connect_selected_signal(self.handle_on_select_annotation)

        self.boxes_on_scene.append(ann_box)

        return ann_box

    @pyqtSlot(object)
    def handle_on_select_annotation(self, ann_box: object):
        if isinstance(ann_box, UAnnotationBox):
            try:
                index = self.boxes_on_scene.index(ann_box)
                if self.commander:
                    self.commander.selected_annotation.emit(index)
            except Exception as error:
                print(str(error))

    def _emit_commander_on_add(self, annotation_data: FAnnotationData):
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
        for box in self.boxes_on_scene:
            box.set_draw_scale(self.scale_factor)

    def delete_on_press_key(self, key: int):
        if key == Qt.Key_Delete:
            items = self.annotate_scene.selectedItems()
            if len(items) <= 0:
                return
            selected_box = items[0]
            if isinstance(selected_box, UAnnotationBox):
                try:
                    index = self.boxes_on_scene.index(selected_box)
                except Exception as error:
                    print(str(error))
                    return
                deleted_data = selected_box.get_annotation_data()
                self.delete_annotation_box(selected_box)
                if self.commander:
                    self.commander.deleted_annotation.emit(self.get_current_thumb_index(), index, deleted_data)

    def delete_annotation_box(self, box: UAnnotationBox):
        if box in self.boxes_on_scene is False or self.current_display_thumbnail is None:
            return
        #delete_index = self.boxes_on_scene.index(box)
        #self.commander.deleted_annotation.emit(self.get_current_thumb_index(), delete_index, box.get_annotation_data())

        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        if box.signal_holder:
            box.signal_holder.disconnect()
            box.signal_holder.deleteLater()
        self.boxes_on_scene.remove(box)
        if box.scene() is not None:
            self.annotate_scene.removeItem(box)
        box.setParentItem(None)

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
        prev_data = selected.get_annotation_data()
        selected.update_annotate_class(self.annotate_class)
        new_data = selected.get_annotation_data()
        if self.commander is not None and self.current_display_thumbnail is not None:
            ann_index = self.boxes_on_scene.index(selected)
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
        if 0 <= index < len(self.boxes_on_scene):
            self.scene().clearSelection()
            self.boxes_on_scene[index].setSelected(True)

    def clean_all_annotations(self, to_emit: bool = False):
        self.scene().clearSelection()
        while self.boxes_on_scene:
            box = self.boxes_on_scene[-1]

            deleted_data = box.get_annotation_data()
            self.delete_annotation_box(box)

            if to_emit:
                self.commander.deleted_annotation.emit(
                    self.get_current_thumb_index(),
                    len(self.boxes_on_scene),
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
        self.boxes_on_scene.clear()

    def mousePressEvent(self, event):
        if self.is_model_annotating and self.work_mode.value != EWorkMode.ForceDragMode.value:
            return
        if self.work_mode.value == EWorkMode.DragMode.value:
            pass
        elif self.work_mode.value == EWorkMode.ForceDragMode.value:
            pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.current_image is None or self.annotate_class is None:
                return super().mousePressEvent(event)
            if self.current_rect is None and self.annotate_start_point is None:
                cursor_pos = self.mapToScene(event.pos())
                self.annotate_start_point = self.current_image.mapFromScene(cursor_pos)
                class_id, name, color = self.annotate_class
                self.current_rect = self.add_annotation_box(
                    self.annotate_start_point.x(),
                    self.annotate_start_point.y(),
                    1,
                    1,
                    (class_id, name, QColor(color)),
                )
            elif self.current_rect is not None and self.annotate_start_point is not None:
                self.delete_annotation_box(self.current_rect)
                self.current_rect = None
                self.annotate_start_point = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_model_annotating and self.work_mode.value != EWorkMode.ForceDragMode.value:
            return
        if self.work_mode.value == EWorkMode.DragMode.value:
            pass
        elif self.work_mode.value == EWorkMode.ForceDragMode.value:
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
        if self.is_model_annotating:
            if self.current_rect is not None:
                self.delete_annotation_box(self.current_rect)
                self.current_rect = None
                return
        if self.work_mode.value == EWorkMode.DragMode.value:
            selected = self.get_selected_annotation_box()
            if selected is None:
                pass
            else:
                index = self.boxes_on_scene.index(selected)
                self.commander.updated_annotation.emit(
                    self.get_current_thumb_index(),
                    index,
                    None,
                    selected.get_annotation_data()
                )
                pass
        elif self.work_mode.value == EWorkMode.AnnotateMode.value:
            if self.current_image is None or self.annotate_class is None:
                pass
            elif self.current_rect is not None and self.annotate_start_point is not None:
                if self.current_rect.get_square() < 25:
                    self.delete_annotation_box(self.current_rect)
                    self.current_rect = None
                    return
                if self.commander is not None:
                    self._emit_commander_on_add(self.current_rect.get_annotation_data())
                    self.current_rect.setSelected(True)
                    self.current_rect = None
                    self.annotate_start_point = None
                    self.commander.change_work_mode.emit(EWorkMode.DragMode.value)

        super().mouseReleaseEvent(event)

    def get_current_thumb_index(self) -> int:
        thumb_index, *_ = self.current_display_thumbnail
        return thumb_index

    def get_annotations(self):
        return self.boxes_on_scene

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