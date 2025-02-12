from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QUrl, QThreadPool, QRunnable, QRectF, QThread
from PyQt5.QtGui import QPixmap, QPen, QImage, QMouseEvent, QColor, QBrush, QTransform
from PyQt5.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel
)

from commander import UGlobalSignalHolder
from utility import FAnnotationData, FClassData, EAnnotationStatus
from annotable import UAnnotationBox

class ImageLoaderThread(QThread):
    image_loaded = pyqtSignal(QPixmap)

    def __init__(self, image_path, width: int, height: int):
        super().__init__()
        self.width = width
        self.height = height
        self.image_path = image_path

    def run(self):
        pixmap = QPixmap(self.image_path).scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #pixmap.scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_loaded.emit(pixmap)

class UAnnotationThumbnail(QGraphicsPixmapItem):
    def __init__(self,
                 image_path: str,
                 height,
                 scale: float,
                 classes: list[FClassData] = None
                 ):
        super().__init__()

        self.setFlag(QGraphicsPixmapItem.ItemIsSelectable)

        try:
            pixmap = QPixmap(image_path)
            self.scale = height / pixmap.height() * scale
            self._height: int = int(pixmap.height() * self.scale)
            self._width: int = int(pixmap.width() * self.scale)
        except Exception:
            self.scale = scale
            self._height = int(height * self.scale)
            self._width = int(height * self.scale)

        self.setPixmap(QPixmap())
        self.uploaded = False

        self.classes = classes

        self.emitter = UPixmapSignalEmitter()

        self.annotation_status : EAnnotationStatus = EAnnotationStatus.NoAnnotation
        self.index = -1
        self.image_path = image_path

        self.board_width = 4
        self.annotation_width = 1

        self.annotation_data_list : list[FAnnotationData] = list()
        self.update()

    def add_annotation(self, data: FAnnotationData):
        self.annotation_data_list.append(data)
        if len(self.annotation_data_list) > 0:
            self.set_annotated_status(EAnnotationStatus.Annotated)
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

        if self.isSelected():
            pen = QPen(Qt.blue)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            if self.annotation_status.value == EAnnotationStatus.MarkedDrop.value:
                painter.setBrush(QColor(255, 0, 0, 50))
            painter.drawRect(self.boundingRect())
        elif self.annotation_status.value == EAnnotationStatus.Annotated.value:
            pen = QPen(Qt.green)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())
        elif self.annotation_status.value == EAnnotationStatus.MarkedDrop.value:
            pen = QPen(Qt.red)
            pen.setWidth(self.board_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 50))
            painter.drawRect(self.boundingRect())

        for ann_data in self.annotation_data_list:
            if 0 <= ann_data.ClassID < len(self.classes):
                color = self.classes[ann_data.ClassID].Color
            else:
                color = FClassData.get_save_color(ann_data.ClassID)
            pen = QPen(color)
            pen.setWidth(self.annotation_width)
            painter.setPen(pen)

            background = QColor(color)
            background.setAlpha(50)
            painter.setBrush(background)

            rect = QRectF(
                ann_data.X * self.scale,
                ann_data.Y * self.scale,
                ann_data.Width * self.scale,
                ann_data.Height * self.scale
            )

            painter.drawRect(rect)

    def boundingRect(self):
        if self.pixmap().isNull():
            return QRectF(0, 0, self._width, self._height)
        else:
            return super().boundingRect()

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

class UPixmapSignalEmitter(QObject):
    clicked = pyqtSignal(UAnnotationThumbnail)
    changed_status = pyqtSignal(EAnnotationStatus, EAnnotationStatus)

    def __init__(self, parent=None):
        super().__init__(parent)

    def emit_signal(self, thumbnail: UAnnotationThumbnail):
        self.clicked.emit(thumbnail)

class UHorizontalScrollView(QGraphicsView):
    view_changed = pyqtSignal(QRectF)

    def get_view_bound_box(self):
        return QRectF(
            self.mapToScene(self.viewport().rect().topLeft()).x() - 400,
            self.mapToScene(self.viewport().rect().topLeft()).y(),
            self.viewport().rect().width() + 600,
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

class UThumbnailCarousel(QWidget):
    signal_thumbnail_select = pyqtSignal(UAnnotationThumbnail)

    def __init__(
            self,
            parent = None,
    ):
        super().__init__(parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.commander: Optional[UGlobalSignalHolder] = None
        self.available_classes: Optional[list[FClassData]] = list()
        self.thumbnails : list [UAnnotationThumbnail] = []
        self.current_selected : Optional[UAnnotationThumbnail] = None

        self.annotated_thumbnails_indexes: list[int] = list()

        self.scene = QGraphicsScene()
        self.view = UHorizontalScrollView(self.scene)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.main_layout.addWidget(self.view)

        self.x_position = 0
        self.y_position = 0
        self.thumbnail_spacing = 20

        self.scale_not_selected = 0.75

        self.view.view_changed.connect(self.display_images)
        self.last_displayed_images: list[UAnnotationThumbnail] = list()

    def set_commander(self, commander: UGlobalSignalHolder):
        if commander is None:
            return
        self.commander = commander

        self.commander.added_new_class.connect(self.add_class)

    def set_available_classes(self, classes: list[FClassData]):
        self.available_classes = classes

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
                self.current_selected = self.thumbnails[0]

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

        print("Index:", self.current_selected.get_index(), "Len:", len(self.thumbnails))

    def add_thumbnail(self, image_path : str):
        thumbnail = UAnnotationThumbnail(
            image_path,
            self.height(),
            self.scale_not_selected,
            self.available_classes
        )
        thumbnail.setTransformationMode(Qt.SmoothTransformation)

        thumbnail.emitter.clicked.connect(self.on_thumbnail_clicked)
        if self.commander:
            thumbnail.emitter.changed_status.connect(self.commander.emit_global_changed_annotation_status)

        self.scene.addItem(thumbnail)
        thumbnail.setPos(self.x_position, self.y_position)

        self.x_position += thumbnail.width() + self.thumbnail_spacing

        thumbnail.set_index(len(self.thumbnails))
        self.thumbnails.append(thumbnail)

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

    def add_class(self, class_data: FClassData):
        if class_data is None:
            return
        self.available_classes.append(class_data)

    def on_thumbnail_clicked(self, thumbnail: UAnnotationThumbnail):
        if self.current_selected is thumbnail:
            return
        self.select_thumbnail(thumbnail)

    def handle_signal_on_update_annotation(self, index: int, data: FAnnotationData):
        if self.current_selected is None:
            return
        self.current_selected.update_annotation(index, data)

    def handle_signal_on_delete_annotation(self, index: int):
        if self.current_selected is None:
            return
        self.current_selected.delete_annotation(index)
        if self.current_selected.annotation_status is False:
            self.annotated_thumbnails_indexes.remove(self.thumbnails.index(self.current_selected))

    def handle_signal_on_added_annotation(self, annotation_box: UAnnotationBox):
        if self.current_selected is None:
            return
        self.current_selected.add_annotation(
            FAnnotationData(
                annotation_box.x(),
                annotation_box.y(),
                annotation_box.width(),
                annotation_box.height(),
                annotation_box.class_id,
                annotation_box.resolution_width(),
                annotation_box.resolution_height()
            )
        )
        print(f"Добавлен бокс с разрешением: {annotation_box.resolution_width()}x{annotation_box.resolution_height()}")
        if self.current_selected.annotation_status is True:
            index = self.thumbnails.index(self.current_selected)
            if index not in self.annotated_thumbnails_indexes:
                self.annotated_thumbnails_indexes.append(index)
                self.annotated_thumbnails_indexes.sort()

    def set_thumbnail_dropped(self, key: int):
        self.current_selected.set_annotated_status(EAnnotationStatus.MarkedDrop)

    def select_thumbnail(self, thumbnail: UAnnotationThumbnail):
        if thumbnail is None:
            return

        self.current_selected = thumbnail
        self.scene.clearSelection()
        self.current_selected.setSelected(True)
        self.view.centerOn(self.current_selected.sceneBoundingRect().center())
        self.signal_thumbnail_select.emit(self.current_selected)

    def update(self):
        super().update()
        self.view.update()
