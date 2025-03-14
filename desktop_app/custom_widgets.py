from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QScrollArea, QWidget, QLabel, QHBoxLayout, QListWidget, \
    QListWidgetItem
from PyQt5.QtCore import Qt

from annotation.annotable import UAnnotationBox, UAnnotationGraphicsView

class UHorizontalScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Устанавливаем горизонтальную полосу прокрутки
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

    def wheelEvent(self, event):
        # Перенаправляем колесо мыши на горизонтальную прокрутку
        if event.angleDelta().y() != 0:  # Убедимся, что движение произошло
            scroll_amount = event.angleDelta().y()  # Извлекаем величину прокрутки
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - scroll_amount
            )
        else:
            super().wheelEvent(event)  # Передаем обработку другим компонентам, если нужно

class UColorLabel(QLabel):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.color = color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color)
        super().paintEvent(event)

class UListAnnotationWidget(QListWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.itemClicked.connect(self.on_item_clicked)

    def clear_list_widget(self):
        while self.count() > 0:
            item = self.takeItem(0)
            widget = self.itemWidget(item)
            if widget:
                widget.deleteLater()
            del item

    def remove_list_item(self, annotation_object: UAnnotationBox):
        if not annotation_object:
            return
        for index in range(self.count()):
            item = self.item(index)
            widget = self.itemWidget(item)

            if widget and hasattr(widget, "annotation_object") and widget.annotation_object == annotation_object:
                widget.deleteLater()
                self.takeItem(index)
                del item
                return

    def add_list_item(self, name, class_id, color: QColor, annotation_object: UAnnotationBox, scene: UAnnotationGraphicsView):
        annotation_widget = UListAnnotationItem(name, class_id, color, annotation_object, scene)
        item = QListWidgetItem(self)
        item.setSizeHint(annotation_widget.sizeHint())
        self.setItemWidget(item, annotation_widget)

    def on_item_clicked(self, item):
        widget = self.itemWidget(item)
        if isinstance(widget, UListAnnotationItem):
            widget.select_scene_object()

class UListAnnotationItem(QWidget):
    def __init__(self, name, obj_id, color: QColor, annotation_object: UAnnotationBox, scene: UAnnotationGraphicsView):
        super().__init__()

        self.annotation_object = annotation_object  # Ссылка на объект на сцене
        self.scene = scene

        # Создаём цветной прямоугольник (UColorLabel с фоном)
        self.color_label = UColorLabel(color)
        self.color_label.setFixedSize(40, 15)  # Размер квадрата

        # Текстовое описание
        self.text_label = QLabel(f"{obj_id}: {name}")
        font = QFont()
        font.setPointSize(12)
        self.text_label.setFont(font)

        # Горизонтальный layout
        layout = QHBoxLayout()
        layout.addWidget(self.color_label)
        layout.addWidget(self.text_label)
        layout.addStretch()  # Чтобы текст не прилипал к краю
        layout.setContentsMargins(5, 2, 5, 2)  # Отступы
        self.setLayout(layout)

    def select_scene_object(self):
        if self.annotation_object and self.scene:
            self.scene.clearSelection()
            self.annotation_object.setSelected(True)  # Выделяем объект на сцене