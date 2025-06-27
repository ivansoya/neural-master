import math
import queue
from collections import OrderedDict
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF, QRect, QObject, pyqtSlot, QMetaObject, Q_ARG, QTimer, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QPixmap, QColor, QImage, QPolygonF
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QGraphicsPixmapItem, QGraphicsProxyWidget, \
    QGraphicsObject

from utility import FAnnotationItem, FDetectAnnotationData, FPolygonAnnotationData, EAnnotationType


class UGraphicsGalleryItem(QGraphicsObject):
    def __init__(self, size: int):
        super().__init__()
        self.selected = False
        self.board_width = 2
        self.size = size
        self.setAcceptedMouseButtons(Qt.LeftButton)

    def isSelected(self):
        return self.selected

    def setSelected(self, selected: bool):
        self.selected = selected
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.size, self.size)

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(Qt.lightGray))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.boundingRect())

    def mousePressEvent(self, event):
        self.selected = not self.selected
        self.update()
        super().mousePressEvent(event)


class UGraphicsAnnotationGalleryItem(UGraphicsGalleryItem):
    signal_clicked = pyqtSignal(int, bool)

    def __init__(self, annotation_data: FAnnotationItem, index: int, selected: bool, size: int):
        super().__init__(size)
        self.annotation_data = annotation_data
        self.index = index
        self.size = size
        self.setSelected(selected)

        self.loaded = False
        self.pixmap: QPixmap | None = None

    def set_image(self, image: QImage):
        if self.loaded:
            return
        self.pixmap = QPixmap(image)
        self.loaded = True
        self.update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.signal_clicked.emit(self.index, self.selected)

    def create_image(self) -> QImage:
        image = QImage(self.annotation_data.get_image_path())
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)

        for annotation in self.annotation_data.annotation_list:
            if isinstance(annotation, FDetectAnnotationData):
                _, _, _, color, (x, y, width, height) = annotation.get_data()
                pen = QPen(color)
                pen.setWidth(int(self.board_width * (image.width() // self.size)))
                painter.setPen(pen)
                painter.drawRect(
                    int(max(0, x)),
                    int(max(0, y)),
                    width,
                    height
                )
            elif isinstance(annotation, FPolygonAnnotationData):
                _, _, _, color, point_list = annotation.get_data()
                pen = QPen(color)
                pen.setWidth(int(self.board_width * (image.width() // self.size)))
                painter.setPen(pen)
                qt_points = [QPointF(x, y) for x, y in point_list]
                painter.drawPolygon(QPolygonF(qt_points))
        painter.end()

        return image.scaled(
            self.size,
            self.size,
            aspectRatioMode=Qt.KeepAspectRatio,
            transformMode=Qt.SmoothTransformation
        )

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor(Qt.lightGray)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.boundingRect())

        if self.pixmap:
            x = (self.size - self.pixmap.width()) // 2
            y = (self.size - self.pixmap.height()) // 2
            painter.drawPixmap(x, y, self.pixmap)

        if self.selected:
            painter.setPen(QPen(QColor(Qt.blue), self.board_width * 2))
            painter.setBrush(QBrush(QColor(0, 0, 255, 30)))
            painter.drawRect(self.boundingRect())

    def get_index(self):
        return self.index

    def get_image_path(self):
        return self.annotation_data.get_image_path()

    def is_loaded(self):
        return self.loaded


class UGalleryImageLoader(QObject):
    # ID и QImage изображения, которое нужно загрузить в галерею
    signal_set_image = pyqtSignal(int, object)
    # Объект UGalleryWidget
    signal_add_widget = pyqtSignal(object)

    def __init__(self, gallery: 'UImageGallery'):
        super().__init__()
        self.gallery = gallery

        self.current_indexes: set[int] = set()

        self.indexes_to_load: set[int] = set()
        self.indexes_to_unload: set[int] = set()

        self.queue_load_images: list[int] = list()
        self.set_load_images: set[int] = set()

        self.timer: Optional[QTimer] = None

    @pyqtSlot()
    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.load_next_image)

    @pyqtSlot(set, bool)
    def update_visibilities(self, updated_indexes: set[int], is_new: bool):
        if is_new:
            self.current_indexes.clear()
        if self.current_indexes == updated_indexes:
            return
        self.indexes_to_load = updated_indexes - self.current_indexes
        self.indexes_to_unload = self.current_indexes - updated_indexes
        self.current_indexes = updated_indexes

        self.create_widgets()
        self.start_load_images()

    def create_widgets(self):
        for index in self.indexes_to_load:
            if not (0 <= index <= len(self.gallery.annotation_data)):
                continue
            widget_gallery = UGraphicsAnnotationGalleryItem(
                self.gallery.annotation_data[index],
                index,
                self.gallery.is_widget_selected_by_id(index),
                self.gallery.cell_size
            )
            self.signal_add_widget.emit(widget_gallery)

    def start_load_images(self):
        for index in self.indexes_to_load:
            if index not in self.set_load_images:
                self.queue_load_images.append(index)

        for index in self.indexes_to_unload:
            if index in self.queue_load_images:
                    self.queue_load_images.remove(index)

        if not self.timer.isActive():
            self.timer.start()

    @pyqtSlot()
    def load_next_image(self):
        if len(self.queue_load_images) == 0:
            self.timer.stop()
            return
        index = self.queue_load_images[0]
        widget: UGraphicsAnnotationGalleryItem = self.gallery.get_widget_by_index(index)
        if widget is None:
            self.queue_load_images.remove(index)
            return
        image = widget.create_image()
        if image.isNull():
            self.queue_load_images.remove(index)
            print(f"Не удалось загрузить изображение {widget.get_image_path()}")
            return
        self.queue_load_images.remove(index)
        self.set_load_images.add(index)
        self.signal_set_image.emit(index, image)

    @pyqtSlot(int)
    def remove_from_loaded(self, index: int):
        self.set_load_images.discard(index)

    @pyqtSlot()
    def clean_all_loaded(self):
        if self.timer.isActive():
            self.timer.stop()
        self.set_load_images.clear()
        self.queue_load_images.clear()


class UImageGallery(QGraphicsView):
    signal_changed_viewport = pyqtSignal(set, bool)
    signal_clear_viewport = pyqtSignal()
    signal_deleted_from_cache = pyqtSignal(int)

    def __init__(self, parent = None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.margin: int = 10
        self.current_margin: int = self.margin
        self.cell_size: int = 200
        self.columns = max(1, self.width() // (self.cell_size + self.margin))

        self.loader_thread = QThread()
        self.image_loader = UGalleryImageLoader(self)
        self.image_loader.signal_add_widget.connect(self.add_item)
        self.image_loader.signal_set_image.connect(self.set_image_by_index)
        self.signal_changed_viewport.connect(self.image_loader.update_visibilities)
        self.signal_clear_viewport.connect(self.image_loader.clean_all_loaded)
        self.signal_deleted_from_cache.connect(self.image_loader.remove_from_loaded)

        self.image_loader.moveToThread(self.loader_thread)
        self.loader_thread.start()
        self.loader_thread.started.connect(self.image_loader.setup_timer)

        self.annotation_data: list[FAnnotationItem] = list()

        self.widget_cache: OrderedDict[int, UGraphicsAnnotationGalleryItem] = OrderedDict()
        self.cache_size: int = 500

        self.set_selected: set[int] = set()
        self.filtered_indexes: dict[int, int] = dict()
        # Словарь для отображения виджетов. Первое значение - ID виджета, Второе - позиция в галерее
        self.dict_displayed_indexes: dict[int, int] = dict()

        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

    @pyqtSlot(object)
    def add_item(self, gallery_item: UGraphicsAnnotationGalleryItem):
        if not isinstance(gallery_item, UGraphicsAnnotationGalleryItem):
            print("Попытка добавить невалидный тип объекта в галерею!")
            return
        index = gallery_item.get_index()
        if index not in self.filtered_indexes:
            return
        if index in self.widget_cache:
            self.widget_cache.move_to_end(index)
            return
        if len(self.widget_cache) >= self.cache_size:
            self.delete_widget_from_cache()
        display_index = self.filtered_indexes[index]
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)
        pos_x = self.margin // 2 + (display_index % self.columns) * (self.cell_size + self.current_margin)
        pos_y = self.margin // 2 + (display_index // self.columns) * (self.cell_size + self.margin)
        #gallery_item.setFixedSize(self.cell_size, self.cell_size)
        gallery_item.setPos(pos_x, pos_y)
        gallery_item.signal_clicked.connect(self.handle_select_image)
        self.scene.addItem(gallery_item)
        self.widget_cache[index] = gallery_item
        #self.viewport().update()

    @pyqtSlot(int, object)
    def set_image_by_index(self, index: int, image: QImage):
        if index not in self.widget_cache:
            return
        self.widget_cache[index].set_image(image)

    @pyqtSlot(int, bool)
    def handle_select_image(self, index: int, selected: bool):
        self.set_selected.add(index) if selected else self.set_selected.discard(index)

    def filter_images(self, image_filter: dict[int, bool], type_list: list[EAnnotationType]):
        if not image_filter or len(image_filter) < 0:
            return
        self.filtered_indexes.clear()
        available_annotations = [index for index, is_available in image_filter.items() if is_available]
        # Устанавливаем список отфильтрованных значений
        for index in range(len(self.annotation_data)):
            class_list = []
            for annotation in self.annotation_data[index].annotation_list:
                if annotation.get_annotation_type() in type_list:
                    class_list.append(annotation.class_id)
            if ((set(class_list) & set(available_annotations) and index not in self.filtered_indexes)
                    or len(self.annotation_data[index].annotation_list) == 0):
                self.filtered_indexes[index] = len(self.filtered_indexes)
        #
        self.update_scene_rect()
        self.update_grid()
        self.update_visibility(True)

    def update_grid(self):
        self.columns = max(1, self.width() // (self.cell_size + self.margin))
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)

        # Обновляем саму сетку с виджетами
        for index, cached_widget in list(self.widget_cache.items()):
            if index not in self.filtered_indexes:
                self.widget_cache.move_to_end(index, last=False)
                cached_widget.setPos(self.margin, -1000)
            else:
                pos_index = self.filtered_indexes[index]
                pos_x = self.margin // 2 + (pos_index % self.columns) * (self.cell_size + self.current_margin)
                pos_y = self.margin // 2 + (pos_index // self.columns) * (self.cell_size + self.margin)
                cached_widget.setPos(pos_x, pos_y)

    def update_visibility(self, force: bool = False):
        viewport_rect = self.viewport().rect()  # Границы viewport в координатах виджета
        scene_rect: QRect = self.mapToScene(viewport_rect).boundingRect()

        index_first = int(scene_rect.y() // (self.cell_size + self.margin) * self.columns)
        index_last = int(index_first + (int(math.ceil(viewport_rect.height() / (self.cell_size + self.margin))) + 1) * self.columns - 1)

        current_visible = [i for i in range(index_first, index_last + 1) if len(self.filtered_indexes) > i >= 0]
        list_visible_index_real = [list(self.filtered_indexes.keys())[index] for index in current_visible]

        self.signal_changed_viewport.emit(set(list_visible_index_real), force)

    def update_scene_rect(self):
        self.scene.setSceneRect(
            0,
            0,
            self.columns * (self.current_margin + self.cell_size) - self.current_margin + self.margin // 2,
            (len(self.filtered_indexes) // self.columns + 1) * (self.cell_size + self.margin)
        )

        vertical_scrollbar = self.verticalScrollBar()
        max_scroll = max(0, self.scene.sceneRect().height() - self.height())

        vertical_scrollbar.setRange(0, int(max_scroll))
        vertical_scrollbar.setPageStep(self.height())  # Размер шага при клике на полосу прокрутки

    def set_dataset_annotations(self, annotation_list: list[FAnnotationItem]):
        self.annotation_data = annotation_list

    def delete_widget_from_cache(self):
        index, item = self.widget_cache.popitem(last=False)
        self.scene.removeItem(item)
        self.signal_deleted_from_cache.emit(index)

    def is_widget_selected_by_id(self, index: int) -> bool:
        return index in self.set_selected

    def get_selected_annotation(self):
        return [self.annotation_data[index] for index in self.filtered_indexes if index in self.set_selected]

    def set_all_selected(self):
        self.set_selected = set([index for index in self.filtered_indexes.keys()])
        for index, widget in self.widget_cache.items():
            if index in self.set_selected:
                widget.setSelected(True)
            else:
                widget.setSelected(False)
        self.update_visibility()

    def clear_all_selections(self):
        self.set_selected.clear()
        for index, widget in self.widget_cache.items():
            widget.setSelected(False)
        self.update_visibility()

    def clear_scene(self):
        self.verticalScrollBar().setValue(0)

        for key, item in self.widget_cache.items():
            self.scene.removeItem(item)
        self.widget_cache.clear()
        self.set_selected.clear()
        self.signal_clear_viewport.emit()
        self.filtered_indexes.clear()
        self.update_scene_rect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_grid()
        self.update_scene_rect()
        self.update_visibility()

    def wheelEvent(self, event):
        super().wheelEvent(event)
        self.update_visibility()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.update_visibility()

    def set_cell_size(self, cell_size: int):
        self.cell_size = cell_size

    def get_cell_size(self):
        return self.cell_size

    def get_widget_by_index(self, index: int) -> UGraphicsAnnotationGalleryItem | None:
        if index not in self.widget_cache:
            return None
        widget = self.widget_cache[index]
        if not isinstance(widget, UGraphicsAnnotationGalleryItem) or widget.is_loaded():
            return None
        return widget

    def set_margin(self, margin: int):
        self.margin = margin
