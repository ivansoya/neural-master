from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QGraphicsPixmapItem, QGraphicsProxyWidget

from utility import FAnnotationItem, FAnnotationClasses

class UWidgetGallery(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.selected: bool = False
        self.is_loaded: bool = False

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
        pen = QPen(Qt.blue if self.selected else Qt.transparent, 2)
        painter.setBrush(brush)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

class UThreadImageLoader(QThread):
    signal_on_load = pyqtSignal(QPixmap)

    def __init__(
            self,
            image_path: str,
            annotation_data: list[tuple[int, int, int, int, QColor]],
            size: int,
    ):
        super().__init__()
        self.is_running = False
        self.size = size
        self.annotation_data = annotation_data
        self.image_path = image_path

        self.line_width = 2

    def run(self):
        if not self.is_running:
            return

        pixmap = QPixmap(self.image_path).scaled(self.size, self.size, transformMode=Qt.SmoothTransformation)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        for annotation in self.annotation_data:
            if not self.is_running:
                return

            x, y, width, height, color = annotation
            pen = QPen(color)
            pen.setWidth(self.line_width)
            painter.setPen(pen)
            painter.drawRect(
                int(max(0, x - width // 2)),
                int(max(0, y - height // 2)),
                width,
                height
            )

        painter.end()
        if self.is_running:
            self.signal_on_load.emit(pixmap)

    def stop(self):
        self.is_running = False

class UAnnotationImage(UWidgetGallery):
    def __init__(
            self,
            image_path: str,
            data: list[tuple[int, int, int, int, QColor]],
            size: int = 200,
            parent = None
    ):
        super().__init__(parent)

        self.image_path = image_path
        self.annotation_data = data
        self.size = size
        self.setFixedSize(self.size, self.size)

        self.pixmap: Optional[QPixmap] = None
        self.thread_load: Optional[UThreadImageLoader] = None

    def on_load(self):
        if self.thread_load and self.thread_load.isRunning():
            return

        self.thread_load = UThreadImageLoader(self.image_path, self.annotation_data, self.size)
        self.thread_load.signal_on_load.connect(self.on_image_loaded)
        self.thread_load.run()
        pass

    def on_image_loaded(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.update()

    def on_unload(self):
        if self.thread_load and self.thread_load.isRunning():
            self.thread_load.stop()
            self.thread_load.quit()

        self.pixmap = None
        self.update()

class UImageGallery(QGraphicsView):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.margin: int = 10
        self.current_margin: int = self.margin
        self.cell_size: int = 200
        self.columns = max(1, self.width() // (self.cell_size + self.margin))
        print(self.width())

        self.widget_map : dict[UWidgetGallery, QGraphicsProxyWidget] = dict()

        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

    def add_item(self, item: UWidgetGallery):
        if item in self.widget_map:
            print(f"Ошибка в функции UImageGallery.add_item! Передаваемый объект уже существует в списке!")
            return
        index = len(self.widget_map)
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)
        pos_x = self.margin // 2 + (index % self.columns) * (self.cell_size + self.current_margin)
        pos_y = self.margin // 2 + (index // self.columns) * (self.cell_size + self.margin)
        proxy = self.scene.addWidget(item)
        proxy.setPos(pos_x, pos_y)
        self.widget_map[item] = proxy

        self.update_scene_rect()

    def update_grid(self):
        self.columns = max(1, self.width() // (self.cell_size + self.margin))
        self.current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)

        if len(self.widget_map) == 0:
            return

        # Обновляем саму сетку с виджетами
        index = 0
        for key, value in self.widget_map.items():
            pos_x = self.margin // 2 + (index % self.columns) * (self.cell_size + self.current_margin)
            pos_y = self.margin // 2 + (index // self.columns) * (self.cell_size + self.margin)
            value.setPos(pos_x, pos_y)
            index += 1

        self.update_scene_rect()


    def update_scene_rect(self):
        self.scene.setSceneRect(
            0,
            0,
            self.columns * (self.current_margin + self.cell_size) - self.current_margin + self.margin // 2,
            (len(self.widget_map) // self.columns + 1) * (self.cell_size + self.margin)
        )

        vertical_scrollbar = self.verticalScrollBar()
        max_scroll = max(0, self.scene.sceneRect().height() - self.height())

        vertical_scrollbar.setRange(0, int(max_scroll))
        vertical_scrollbar.setPageStep(self.height())  # Размер шага при клике на полосу прокрутки

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_grid()

    def set_cell_size(self, cell_size: int):
        self.cell_size = cell_size

    def get_cell_size(self):
        return self.cell_size

    def set_margin(self, margin: int):
        self.margin = margin