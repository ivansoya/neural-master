import math
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF, QRect
from PyQt5.QtGui import QPainter, QPen, QBrush, QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QGraphicsPixmapItem, QGraphicsProxyWidget

class UThreadImageLoader(QThread):
    signal_on_load = pyqtSignal(QPixmap)

    def __init__(
            self,
            image_path: str,
            annotation_data: list[tuple[int, int, int, int, int, QColor]],
            show_dict: dict[int, bool],
            size: int,
    ):
        super().__init__()
        self.is_running = True
        self.size = size
        self.show_dict = show_dict
        self.annotation_data = annotation_data
        self.image_path = image_path

        self.line_width = 2

    def run(self):
        if not self.is_running:
            return

        pixmap = QPixmap(self.image_path)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        for annotation in self.annotation_data:
            if not self.is_running:
                return
            try:
                class_id, x, y, width, height, color = annotation
                if self.show_dict[class_id] is False:
                    continue
                pen = QPen(color)
                pen.setWidth(int(self.line_width * (pixmap.width() // self.size)))
                painter.setPen(pen)
                painter.drawRect(
                    int(max(0, x - width // 2)),
                    int(max(0, y - height // 2)),
                    width,
                    height
                )
            except Exception as error:
                print(str(error))
                continue

        painter.end()
        scaled_pixmap = pixmap.scaled(
            self.size,
            self.size,
            aspectRatioMode=Qt.KeepAspectRatio,
            transformMode=Qt.SmoothTransformation
        )
        if self.is_running:
            self.signal_on_load.emit(scaled_pixmap)

    def stop(self):
        self.is_running = False

class UWidgetGallery(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.selected: bool = False
        self.is_loaded: bool = False

        self.board_width: int = 2

    def set_loaded(self, loaded):
        if self.is_loaded is loaded:
            return
        if loaded is True:
            self.is_loaded = True
            self.on_load()
        else:
            self.is_loaded = False
            self.on_unload()

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def isSelected(self):
        return self.selected

    def setSelected(self, selected: bool):
        self.selected = selected

    def mousePressEvent(self, event):
        self.selected = not self.selected
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        brush = QBrush(Qt.lightGray)
        pen = QPen(Qt.blue if self.selected else Qt.transparent, self.board_width)
        painter.setBrush(brush)
        painter.setPen(pen)
        t_width: int = self.board_width // 2
        painter.drawRect(self.rect().adjusted(t_width, t_width, -t_width, -t_width))

class UAnnotationImage(UWidgetGallery):
    def __init__(
            self,
            image_path: str,
            dataset: str,
            data: list[tuple[int, int, int, int, int, QColor]],
            show_dict: dict[int, bool],
            size: int = 200,
            parent = None
    ):
        super().__init__(parent)

        self.image_path = image_path
        self.dataset = dataset
        self.annotation_data = data
        self.size = size
        self.setFixedSize(self.size, self.size)
        self.show_dict = show_dict

        self.pixmap: Optional[QPixmap] = None
        self.thread_load: Optional[UThreadImageLoader] = None

    def on_load(self):
        if self.thread_load and self.thread_load.isRunning():
            return
        self.thread_load = UThreadImageLoader(self.image_path, self.annotation_data, self.show_dict, self.size)
        self.thread_load.signal_on_load.connect(self.on_image_loaded)
        self.thread_load.run()

    def on_image_loaded(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.update()

    def on_unload(self):
        if self.thread_load and self.thread_load.isRunning():
            self.thread_load.stop()
            self.thread_load.quit()
            self.thread_load.deleteLater()

        self.pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.pixmap:
            x = (self.width() - self.pixmap.width()) // 2
            y = (self.height() - self.pixmap.height()) // 2
            painter.drawPixmap(x, y, self.pixmap)

        if self.selected:
            pen = QPen(Qt.blue, self.board_width * 2)
            brush = QBrush(QColor(0, 0, 255, 30))
            painter.setBrush(brush)
            painter.setPen(pen)
            painter.drawRect(self.rect())

    def get_dataset_name(self):
        return self.dataset

    def get_class_id(self):
        return self.class_id

    def is_show(self):
        try:
            to_show = False
            for annotation in self.annotation_data:
                class_id, *_ = annotation
                to_show = self.show_dict[class_id]
            return to_show
        except Exception as error:
            print(str(error))
            return False

class UImageGallery(QGraphicsView):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.margin: int = 10
        self.current_margin: int = self.margin
        self.cell_size: int = 300
        self.columns = max(1, self.width() // (self.cell_size + self.margin))

        self.list_widgets : list[QGraphicsProxyWidget] = list()
        self.list_displayed_indexes: list[int] = list()
        self.last_visible = list()

        self.filter: Optional[dict[int, bool]] = None

        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

    def add_item(self, item: UWidgetGallery):
        if not isinstance(item, UWidgetGallery):
            print("Попытка добавить невалидный тип объекта в галерею!")
            return
        if item in self.list_widgets:
            print(f"Ошибка в функции UImageGallery.add_item! Передаваемый объект уже существует в списке!")
            return
        index = len(self.list_widgets)
        display_index = len(self.list_displayed_indexes)
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)
        pos_x = self.margin // 2 + (display_index % self.columns) * (self.cell_size + self.current_margin)
        pos_y = self.margin // 2 + (display_index // self.columns) * (self.cell_size + self.margin)
        proxy = self.scene.addWidget(item)
        proxy.setPos(pos_x, pos_y)
        self.list_widgets.append(proxy)
        self.list_displayed_indexes.append(index)
        self.update_scene_rect()

    def update_grid(self, filter_dict: dict[int, bool] = None):
        if filter_dict != self.filter:
            self.filter = filter_dict.copy()
            self._set_widgets_load_by_indexes(self.last_visible, False)
            self.last_visible = []
        self.columns = max(1, self.width() // (self.cell_size + self.margin))
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)

        if len(self.list_widgets) == 0:
            return

        # Обновляем саму сетку с виджетами
        index = 0
        current_display_index = -1
        self.list_displayed_indexes.clear()
        for item in self.list_widgets:
            widget = item.widget()
            if self.filter is not None and isinstance(widget, UAnnotationImage):
                try:
                    if widget.is_show() is True:
                        current_display_index += 1
                        self.list_displayed_indexes.append(index)
                    else:
                        item.setPos(-1000, -1000)
                        index += 1
                        continue
                except Exception as error:
                    print(str(error))
                    pass
            else:
                current_display_index += 1
                self.list_displayed_indexes.append(current_display_index)


            pos_x = self.margin // 2 + (current_display_index  % self.columns) * (self.cell_size + self.current_margin)
            pos_y = self.margin // 2 + (current_display_index  // self.columns) * (self.cell_size + self.margin)
            item.setPos(pos_x, pos_y)
            index += 1

        self.update_scene_rect()
        self.update_visibility()

    def update_scene_rect(self):
        self.scene.setSceneRect(
            0,
            0,
            self.columns * (self.current_margin + self.cell_size) - self.current_margin + self.margin // 2,
            (len(self.list_displayed_indexes) // self.columns + 1) * (self.cell_size + self.margin)
        )

        vertical_scrollbar = self.verticalScrollBar()
        max_scroll = max(0, self.scene.sceneRect().height() - self.height())

        vertical_scrollbar.setRange(0, int(max_scroll))
        vertical_scrollbar.setPageStep(self.height())  # Размер шага при клике на полосу прокрутки

    def update_visibility(self, force: bool = False):
        if force:
            self.last_visible = []
            self.centerOn(0, 0)

        viewport_rect = self.viewport().rect()  # Границы viewport в координатах виджета
        scene_rect: QRect = self.mapToScene(viewport_rect).boundingRect()

        index_first = int(scene_rect.y() // (self.cell_size + self.margin) * self.columns)
        index_last = int(index_first + (int(math.ceil(viewport_rect.height() / (self.cell_size + self.margin))) + 1) * self.columns - 1)

        current_visible = [i for i in range(index_first, index_last + 1) if len(self.list_displayed_indexes) > i >= 0]

        if current_visible == self.last_visible:
            return

        diff_loaded = list(set(current_visible) - set(self.last_visible))
        diff_unloaded = list(set(self.last_visible) - set(current_visible))

        self._set_widgets_load_by_indexes(diff_loaded, True)
        self._set_widgets_load_by_indexes(diff_unloaded, False)

        self.last_visible = current_visible

    def get_selected_widgets(self):
        return  [item for item in self.scene.selectedItems() if isinstance(item, UWidgetGallery)]

    def clear_scene(self):
        self.verticalScrollBar().setValue(0)
        for item in self.list_widgets[::-1]:
            self.scene.removeItem(item)
            self.list_widgets.remove(item)
        self.list_displayed_indexes.clear()
        self.update_scene_rect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_grid(self.filter)

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

    def set_margin(self, margin: int):
        self.margin = margin

    def _set_widgets_load_by_indexes(self, widget_indexes: list[int], loaded: bool):
        for index in widget_indexes:
            try:
                widget = self.list_widgets[self.list_displayed_indexes[index]].widget()
                if isinstance(widget, UWidgetGallery):
                    widget.set_loaded(loaded)
            except Exception as error:
                print(str(error))
                continue