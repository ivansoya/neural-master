from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QPixmap
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QGraphicsPixmapItem, QGraphicsProxyWidget

from utility import FAnnotationItem


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

class UAnnotationImageLoader(QThread):
    signal_on_load = pyqtSignal(QPixmap)

    def __init__(self, annotation: FAnnotationItem):
        super().__init__()
        self.annotation = annotation

    def run(self):
        pass

class UAnnotationImageGallery(QGraphicsPixmapItem, UWidgetGallery):
    def __init__(self, annotation: FAnnotationItem, parent = None):
        super().__init__(parent)
        self.annotation = annotation
        self.thread_load: Optional[UAnnotationImageLoader] = None

    def on_load(self):
        pass

    def on_unload(self):
        pass

class UImageGallery(QGraphicsView):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.columns: int = 1
        self.margin: int = 10
        self.cell_size: int = 200

        self.widget_map : dict[UWidgetGallery, QGraphicsProxyWidget] = dict()

        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

    def add_item(self, item: UWidgetGallery):
        if item in self.widget_map:
            print(f"Ошибка в функции UImageGallery.add_item! Передаваемый объект уже существует в списке!")
            return
        index = len(self.widget_map)
        current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)
        pos_x = self.margin // 2 + (index % self.columns) * (self.cell_size + current_margin)
        pos_y = self.margin // 2 + (index // self.columns) * (self.cell_size + current_margin)
        proxy = self.scene.addWidget(item)
        proxy.setPos(pos_x, pos_y)
        self.widget_map[item] = proxy

    def update_grid(self):
        if len(self.widgets) == 0:
            return

        # Обновляем саму сетку с виджетами
        self.columns = max(1, self.width() // (self.cell_size + self.margin))
        current_margin = max(self.margin, (self.width() - self.cell_size * self.columns - self.margin) // self.margin)
        index = 0
        for key, value in self.widget_map.items():
            pos_x = self.margin // 2 + (index % self.columns) * (self.cell_size + current_margin)
            pos_y = self.margin // 2 + (index // self.columns) * (self.cell_size + current_margin)
            value.setPos(pos_x, pos_y)
            index += 1

        # Обновляем область сцены
        scene_rect = self.scene.sceneRect()
        self.scene.setSceneRect(scene_rect)

        # Обновляем вертикальный скроллбар
        vertical_scrollbar = self.verticalScrollBar()
        max_scroll = max(0, scene_rect.height() - self.height())
        vertical_scrollbar.setRange(0, max_scroll)
        vertical_scrollbar.setPageStep(self.height())
        vertical_scrollbar.setSingleStep(self.cell_size + self.margin)

    def set_cell_size(self, cell_size: int):
        self.cell_size = cell_size

    def set_margin(self, margin: int):
        self.margin = margin