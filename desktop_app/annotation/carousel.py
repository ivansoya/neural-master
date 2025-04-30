from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF, QThread, QRect, pyqtSlot
from PyQt5.QtGui import QPixmap, QPen, QColor, QBrush, QFont
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QWidget, QVBoxLayout
)

from annotation.annotation_box import UAnnotationBox
from commander import UAnnotationSignalHolder
from utility import FAnnotationData, EAnnotationStatus, FAnnotationClasses, FAnnotationItem


class ImageLoaderThread(QThread):
    image_loaded = pyqtSignal(QPixmap)

    def __init__(self, image_path, width: int, height: int):
        super().__init__()
        self.width = width
        self.height = height
        self.image_path = image_path

    def run(self):
        try:
            pixmap = QPixmap(self.image_path).scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_loaded.emit(pixmap)
        except Exception:
            self.image_loaded.emit(None)
            return

class UPixmapSignalEmitter(QObject):
    clicked = pyqtSignal(object)
    changed_status = pyqtSignal(int, EAnnotationStatus, EAnnotationStatus)

    def __init__(self, parent=None):
        super().__init__(parent)

    def emit_signal(self, thumbnail: 'UAnnotationThumbnail'):
        self.clicked.emit(thumbnail)

class UAnnotationThumbnail(QGraphicsPixmapItem):
    def __init__(
            self,
            width: int,
            height: int,
            image_path: str,
            dataset: str | None,
            annotation_data: list[FAnnotationData]
    ):
        super().__init__()

        self.setFlag(QGraphicsPixmapItem.ItemIsSelectable)

        self.setPixmap(QPixmap())
        self.uploaded = False

        self.data = annotation_data
        self.dataset = dataset

        self._width = width
        self._height = height

        self.emitter = UPixmapSignalEmitter()

        self.annotation_status : EAnnotationStatus = EAnnotationStatus.NoAnnotation
        self.index = -1
        self.image_path = image_path

        self.board_width = 4
        self.annotation_width = 1

        self.annotation_data_list: list[FAnnotationData] = annotation_data
        self.update()

    def get_annotation_data(self):
        return self.annotation_data_list

    def add_annotation(self, data: FAnnotationData):
        self.annotation_data_list.append(data)
        if len(self.annotation_data_list) > 0:
            self.set_annotated_status(EAnnotationStatus.Annotated)
        self.update()

    def clear_annotations(self):
        self.annotation_data_list.clear()
        self.set_annotated_status(EAnnotationStatus.NoAnnotation)
        self.update()

    def delete_annotation(self, index: int):
        if index < 0 or index >= len(self.annotation_data_list):
            return
        self.annotation_data_list.pop(index)
        if len(self.annotation_data_list) <= 0 and self.annotation_status.value != EAnnotationStatus.MarkedDrop.value:
             self.set_annotated_status(EAnnotationStatus.NoAnnotation)
        self.update()

    def update_annotation(self, index: int, data: FAnnotationData):
        if index < 0 or index >= len(self.annotation_data_list):
            return
        self.annotation_data_list[index] = data
        self.set_annotated_status(EAnnotationStatus.Annotated)
        self.update()

    def upload_image(self):
        if self.uploaded is True:
            return
        if hasattr(self, 'loader_thread') and self.loader_thread.isRunning():
            return
        self.loader_thread = ImageLoaderThread(self.image_path, self._width, self._height)
        self.loader_thread.image_loaded.connect(self._set_pixmap)
        self.loader_thread.start()

    def _set_pixmap(self, pixmap: QPixmap):
        self.setPixmap(pixmap)
        self.setOffset(
            (self.width() - pixmap.width()) / 2,
            (self.height() - pixmap.height()) / 2
        )
        self.update()
        self.uploaded = True

    def clear_image(self):
        self.setPixmap(QPixmap())
        self.update()
        self.uploaded = False

    def paint(self, painter, option, widget):
        if not self.pixmap().isNull():
            painter.drawPixmap(0, 0, self.pixmap())
        else:
            painter.setBrush(QBrush(QColor(192, 192, 192)))
            painter.drawRect(self.boundingRect())

        for ann_data in self.annotation_data_list:
            color = ann_data.get_color()
            pen = QPen(color)
            pen.setWidth(self.annotation_width)
            painter.setPen(pen)

            background = QColor(color)
            background.setAlpha(50)
            painter.setBrush(background)

            res_w, _ = ann_data.get_resolution()
            scale = float(self.width()) / res_w
            rect = ann_data.get_rect_to_draw()
            scaled_rect = QRect(
                int(rect.x() * scale),
                int(rect.y() * scale),
                int(rect.width() * scale),
                int(rect.height() * scale),
            )

            painter.drawRect(scaled_rect)

        if self.isSelected():
            pen = QPen(Qt.blue)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.transparent)
            painter.drawRect(self.boundingRect())
        elif self.annotation_status.value == EAnnotationStatus.PerformingAnnotation.value:
            pen = QPen(Qt.gray)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())
        elif self.annotation_status.value == EAnnotationStatus.Annotated.value:
            pen = QPen(Qt.green)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 255, 0, 50))
            painter.drawRect(self.boundingRect())
        elif self.annotation_status.value == EAnnotationStatus.MarkedDrop.value:
            pen = QPen(Qt.red)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 50))
            painter.drawRect(self.boundingRect())

        if self.annotation_status.value == EAnnotationStatus.PerformingAnnotation.value:
            painter.setPen(Qt.black)
            painter.setBrush(QColor(0, 0, 0, 50))
            painter.drawRect(self.boundingRect())

            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 12))
            text = "Разметка..."
            text_rect = painter.fontMetrics().boundingRect(text)
            text_x = (self.width() - text_rect.width()) // 2
            text_y = (self.height() - text_rect.height()) // 2
            painter.drawText(int(text_x), int(text_y), text)

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def get_annotated_status(self):
        return self.annotation_status

    def set_annotated_status(self, status: EAnnotationStatus):
        if self.annotation_status.value == status.value:
            pass
        else:
            self.emitter.changed_status.emit(self.index, self.annotation_status, status)
            self.annotation_status = status
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.emitter.emit_signal(self)
        super().mousePressEvent(event)

    def width(self):
        return self.sceneBoundingRect().width()

    def height(self):
        return self.sceneBoundingRect().height()

    def set_index(self, index):
        self.index = index

    def get_index(self):
        return self.index

    def get_image_path(self):
        return self.image_path

    def get_dataset(self):
        return self.dataset

class UThumbnailCarousel(QGraphicsView):
    view_changed = pyqtSignal(QRectF)

    def __init__(
            self,
            parent = None,
    ):
        super().__init__(parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.commander: Optional[UAnnotationSignalHolder] = None
        self.thumbnails : list [UAnnotationThumbnail] = []
        self.current_selected : Optional[UAnnotationThumbnail] = None

        self.annotated_thumbnails_indexes: set[int] = set()
        self.dropped_thumbnails_indexes: set[int] = set()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        #self.main_layout.addWidget(self.view)

        self.y_position = 0
        self.thumbnail_spacing = 10
        self.x_position = self.thumbnail_spacing

        self.scale_not_selected = 0.75

        self.view_changed.connect(self.display_images)
        self.last_displayed_images: list[UAnnotationThumbnail] = list()

    def get_view_bound_box(self):
        return QRectF(
            self.mapToScene(self.viewport().rect().topLeft()).x() - 400,
            self.mapToScene(self.viewport().rect().topLeft()).y(),
            self.viewport().rect().width() + 800,
            self.viewport().rect().height()
        )

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - delta
        )
        self.view_changed.emit(self.get_view_bound_box())

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.view_changed.emit(self.get_view_bound_box())

    def keyPressEvent(self, event):
        pass

    def set_commander(self, commander: UAnnotationSignalHolder):
        if commander is None:
            return
        self.commander = commander

        self.commander.added_new_annotation.connect(self.handle_signal_on_added_annotation)
        self.commander.deleted_annotation.connect(self.handle_signal_on_delete_annotation)
        self.commander.updated_annotation.connect(self.handle_signal_on_update_annotation)

    def clear_thumbnails(self):
        self.scene.clear()  # удаляет все элементы со сцены

        self.thumbnails.clear()
        self.last_displayed_images.clear()
        self.annotated_thumbnails_indexes.clear()
        self.dropped_thumbnails_indexes.clear()

        self.current_selected = None
        self.x_position = 0
        self.y_position = 0

    def select_thumbnail_by_arrow(self, arrow: int):
        if self.current_selected is None:
            if len(self.thumbnails) <= 0:
                # код для ошибки
                return
            else:
                self.select_thumbnail(self.thumbnails[0])

        index = self.current_selected.get_index()
        if index < 0 or index >= len(self.thumbnails):
            # код для ошибки
            return

        if arrow == Qt.Key_Right or arrow == Qt.Key_D:
            if index >= len(self.thumbnails) - 1:
                return
            else:
                self.select_thumbnail(self.thumbnails[index + 1])
        if arrow == Qt.Key_Left or arrow == Qt.Key_A:
            if index <= 0:
                return
            else:
                self.select_thumbnail(self.thumbnails[index - 1])

    def add_thumbnail(self, thumbnail: UAnnotationThumbnail):
        thumbnail.setTransformationMode(Qt.SmoothTransformation)

        thumbnail.emitter.clicked.connect(self.on_thumbnail_clicked)
        thumbnail.emitter.changed_status.connect(self.handle_on_thumbnail_status_changed)

        self.scene.addItem(thumbnail)
        thumbnail.setPos(self.x_position, self.y_position)

        self.x_position += thumbnail.width() + self.thumbnail_spacing

        thumbnail.set_index(len(self.thumbnails))
        self.thumbnails.append(thumbnail)
        if thumbnail.get_annotated_status().value == EAnnotationStatus.Annotated.value:
            self.annotated_thumbnails_indexes.add(thumbnail.get_index())
        elif thumbnail.get_annotated_status().value == EAnnotationStatus.MarkedDrop.value:
            self.dropped_thumbnails_indexes.add(thumbnail.get_index())

        if len(self.thumbnails) == 1 and self.current_selected is None:
            self.select_thumbnail(self.thumbnails[0])
        return thumbnail

    def get_annotation_data_by_index(self, index: int) -> list[FAnnotationData] | None:
        if 0 <= index < len(self.thumbnails):
            return self.thumbnails[index].get_annotation_data()

    @pyqtSlot(int, EAnnotationStatus, EAnnotationStatus)
    def handle_on_thumbnail_status_changed(self, index: int, previous: EAnnotationStatus, current: EAnnotationStatus):
        if current.value == EAnnotationStatus.Annotated.value:
            self.annotated_thumbnails_indexes.add(index)
        elif current.value == EAnnotationStatus.MarkedDrop.value:
            self.dropped_thumbnails_indexes.add(index)

        if previous.value == EAnnotationStatus.Annotated.value:
            if index in self.annotated_thumbnails_indexes:
                self.annotated_thumbnails_indexes.remove(index)
        elif previous.value == EAnnotationStatus.MarkedDrop.value:
            if index in self.dropped_thumbnails_indexes:
                self.dropped_thumbnails_indexes.remove(index)
        if self.commander:
            self.commander.change_status_thumbnail.emit(previous, current)

    def display_images(self, display_bounds: QRectF):
        items = self.scene.items(display_bounds, Qt.IntersectsItemBoundingRect)
        selected_thumbnails: list[UAnnotationThumbnail] = list()
        for thumbnail in items:
            if isinstance(thumbnail, UAnnotationThumbnail):
                selected_thumbnails.append(thumbnail)

        # Отображение картинок в карусели
        for thumb in selected_thumbnails:
            if thumb not in self.last_displayed_images:
                thumb.upload_image()

        # Скрытие картинок:
        for thumb in self.last_displayed_images:
            if thumb not in selected_thumbnails:
                thumb.clear_image()

        self.last_displayed_images.clear()
        self.last_displayed_images = [item for item in selected_thumbnails]

    def add_class(self, name: str):
        return self.available_classes.add_class_by_name(name)

    def on_thumbnail_clicked(self, thumbnail: UAnnotationThumbnail):
        if self.current_selected is thumbnail:
            return
        self.select_thumbnail(thumbnail)

    @pyqtSlot(int, int, object, object)
    def handle_signal_on_update_annotation(
            self,
            index_thumb: int,
            index_annotation: int,
            prev_annotation: None | FAnnotationData,
            annotation_data):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        if isinstance(annotation_data, FAnnotationData):
            self.thumbnails[index_thumb].update_annotation(index_annotation, annotation_data)

    @pyqtSlot(int, int, object)
    def handle_signal_on_delete_annotation(self, index_thumb: int, index_annotation: int, data: FAnnotationData):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        self.thumbnails[index_thumb].delete_annotation(index_annotation)

    @pyqtSlot(int, object)
    def handle_signal_on_added_annotation(self, index_thumb: int, annotation_data):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        if isinstance(annotation_data, FAnnotationData):
            self.thumbnails[index_thumb].add_annotation(annotation_data)

    @pyqtSlot(int)
    def handle_on_adding_thumb_to_model(self, index: int):
        if 0 <= index <= len(self.thumbnails):
            self.thumbnails[index].set_annotated_status(EAnnotationStatus.PerformingAnnotation)

    @pyqtSlot(int, list)
    def handle_on_getting_result_from_model(self, index: int, ann_list: list[FAnnotationData]):
        if 0 <= index <= len(self.thumbnails):
            self.thumbnails[index].clear_annotations()
            if len(ann_list) > 0:
                for annotation in ann_list:
                    self.thumbnails[index].add_annotation(annotation)
            else:
                self.thumbnails[index].set_annotated_status(EAnnotationStatus.MarkedDrop)

    def set_thumbnail_dropped(self):
        if self.current_selected:
            self.current_selected.set_annotated_status(EAnnotationStatus.MarkedDrop)

    def select_thumbnail(self, thumbnail: UAnnotationThumbnail):
        if thumbnail is None:
            return

        self.current_selected = thumbnail
        self.scene.clearSelection()
        self.current_selected.setSelected(True)
        self.centerOn(self.current_selected.sceneBoundingRect().center())
        self.commander.selected_thumbnail.emit(
            (
                thumbnail.get_index(),
                thumbnail.get_image_path(),
                thumbnail.get_annotation_data()
            ),
            thumbnail.get_annotated_status().value
        )

    def get_annotations(self):
        list_annotation_items: list[FAnnotationItem] = list()
        list_annotation_none_dataset: list[FAnnotationItem] = list()
        list_annotations_to_delete: list[FAnnotationItem] = list()

        for index, status_check, target_list in [
            (self.annotated_thumbnails_indexes, EAnnotationStatus.Annotated, list_annotation_items),
            (self.dropped_thumbnails_indexes, EAnnotationStatus.MarkedDrop, list_annotations_to_delete),
        ]:
            for i in index:
                thumb = self.thumbnails[i]
                if thumb.get_annotated_status().value != status_check.value:
                    continue

                dataset = thumb.get_dataset()
                if target_list is list_annotations_to_delete and dataset is None:
                    continue

                ann_item = FAnnotationItem(
                    list(thumb.get_annotation_data()),
                    thumb.get_image_path(),
                    dataset
                )
                if target_list is list_annotation_items and dataset is None:
                    list_annotation_none_dataset.append(ann_item)
                else:
                    target_list.append(ann_item)

        return list_annotation_items, list_annotation_none_dataset, list_annotations_to_delete

    def get_current_thumbnail_status(self):
        if self.current_selected:
            return self.current_selected.get_annotated_status()

    def update(self):
        super().update()
        self.scene.setSceneRect(
            0,
            0,
            self.thumbnail_spacing + len(self.thumbnails) * (200 + self.thumbnail_spacing),
            self.scene.height()
        )
        self.viewport().update()