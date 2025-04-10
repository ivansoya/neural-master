from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF, QThread, QRect
from PyQt5.QtGui import QPixmap, QPen, QColor, QBrush, QFont
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QWidget, QVBoxLayout
)

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

class UAnnotationThumbnail(QGraphicsPixmapItem):
    def __init__(
            self,
            width: int,
            height: int,
            image_path: str,
            dataset: str | None,
            annotation_data: list[FAnnotationData] = None
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

        if annotation_data is None:
            self.annotation_data_list: list[FAnnotationData] = list()
        else:
            self.annotation_data_list : list[FAnnotationData] = annotation_data
            self.annotation_status = EAnnotationStatus.Annotated
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
            self.emitter.changed_status.emit(self.annotation_status, status)
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

class UPixmapSignalEmitter(QObject):
    clicked = pyqtSignal(UAnnotationThumbnail)
    changed_status = pyqtSignal(EAnnotationStatus, EAnnotationStatus)

    def __init__(self, parent=None):
        super().__init__(parent)

    def emit_signal(self, thumbnail: UAnnotationThumbnail):
        self.clicked.emit(thumbnail)

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

        self.annotated_thumbnails_indexes: list[int] = list()

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
        self.thumbnails.clear()
        self.current_selected = None
        self.x_position = 0
        self.y_position = 0
        for thumb in self.scene.items():
            self.scene.removeItem(thumb)
        self.scene.clear()

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
        if self.commander:
            thumbnail.emitter.changed_status.connect(self.commander.emit_global_changed_annotation_status)

        self.scene.addItem(thumbnail)
        thumbnail.setPos(self.x_position, self.y_position)

        self.x_position += thumbnail.width() + self.thumbnail_spacing

        thumbnail.set_index(len(self.thumbnails))
        self.thumbnails.append(thumbnail)
        if thumbnail.get_annotated_status().value == EAnnotationStatus.Annotated.value:
            self.annotated_thumbnails_indexes.append(thumbnail.get_index())

        if len(self.thumbnails) == 1 and self.current_selected is None:
            self.select_thumbnail(self.thumbnails[0])

        return thumbnail

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

    def handle_signal_on_update_annotation(self, index_thumb: int, index_annotation: int, data: FAnnotationData):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        self.thumbnails[index_thumb].update_annotation(index_annotation, data)

    def handle_signal_on_delete_annotation(self, index_thumb: int, index_annotation: int):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        self.thumbnails[index_thumb].delete_annotation(index_annotation)
        if not self.current_selected.annotation_status.value == EAnnotationStatus.Annotated.value:
            if index_thumb in self.annotated_thumbnails_indexes:
                self.annotated_thumbnails_indexes.remove(index_thumb)

    def handle_signal_on_added_annotation(self, index_thumb: int, annotation_data: FAnnotationData):
        if not 0 <= index_thumb < len(self.thumbnails):
            return
        self.thumbnails[index_thumb].add_annotation(annotation_data)
        if self.thumbnails[index_thumb].annotation_status.value == EAnnotationStatus.Annotated.value:
            if not index_thumb in self.annotated_thumbnails_indexes:
                self.annotated_thumbnails_indexes.append(index_thumb)

    def handle_on_adding_thumb_to_model(self, index: int):
        if 0 <= index <= len(self.thumbnails):
            self.thumbnails[index].set_annotated_status(EAnnotationStatus.PerformingAnnotation)

    def handle_on_getting_result_from_model(self, index: int, ann_list: list[FAnnotationData]):
        if 0 <= index <= len(self.thumbnails):
            self.thumbnails[index].clear_annotations()
            if len(ann_list) > 0:
                self.thumbnails[index].set_annotated_status(EAnnotationStatus.Annotated)
                for annotation in ann_list:
                    self.thumbnails[index].add_annotation(annotation)
                if index not in self.annotated_thumbnails_indexes:
                    self.annotated_thumbnails_indexes.append(index)
            else:
                if index in self.annotated_thumbnails_indexes:
                    self.annotated_thumbnails_indexes.remove(index)
                self.thumbnails[index].set_annotated_status(EAnnotationStatus.MarkedDrop)

    def set_thumbnail_dropped(self, key: int):
        if self.current_selected:
            index = self.current_selected.get_index()
            if index in self.annotated_thumbnails_indexes:
                self.annotated_thumbnails_indexes.remove(index)
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
        list_annotations_none_dataset: list[FAnnotationItem] = list()
        for index in self.annotated_thumbnails_indexes:
            if not self.thumbnails[index].get_annotated_status().value == EAnnotationStatus.Annotated.value:
                continue
            data_t = list(self.thumbnails[index].get_annotation_data())
            image_path = self.thumbnails[index].get_image_path()
            dataset = self.thumbnails[index].get_dataset()
            ann_item = FAnnotationItem(data_t, image_path, dataset)
            if dataset is None:
                list_annotations_none_dataset.append(ann_item)
            else:
                list_annotation_items.append(ann_item)

        return list_annotation_items, list_annotations_none_dataset

    def update(self):
        super().update()
        self.scene.setSceneRect(
            0,
            0,
            self.thumbnail_spacing + len(self.thumbnails) * (200 + self.thumbnail_spacing),
            self.scene.height()
        )
        self.viewport().update()