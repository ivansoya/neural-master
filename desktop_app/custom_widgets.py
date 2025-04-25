from collections import OrderedDict

from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QScrollArea, QWidget, QLabel, QHBoxLayout, QListWidget, \
    QListWidgetItem
from PyQt5.QtCore import Qt

from annotation.annotation_scene import UAnnotationBox, UAnnotationGraphicsView

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

    def update_color(self, color: QColor):
        self.color = QColor(color)
        self.update()

class UListAnnotationWidget(QListWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.itemClicked.connect(self.on_item_clicked)

    def select_item(self, index: int):
        if not (0 <= index < self.count()):
            return

        self.setCurrentItem(self.item(index))

    def clear_list_widget(self):
        while self.count() > 0:
            item = self.takeItem(0)
            widget = self.itemWidget(item)
            if widget:
                widget.deleteLater()
            del item

    def remove_list_item(self, index: int):
        if index < 0 or index >= self.count():
            return

        item = self.item(index)
        widget = self.itemWidget(item)
        if not (widget and isinstance(widget, UListAnnotationItem)):
            return

        widget.deleteLater()
        self.takeItem(index)
        del item

        self._update_item_indexes()

    def update_list_item(self, index: int, name: str, color: QColor, box: UAnnotationBox):
        if not (0 <= index < self.count()):
            return

        widget = self.itemWidget(self.item(index))
        if not (widget and isinstance(widget, UListAnnotationItem)):
            return

        widget.set_name(name)
        widget.set_color(color)
        widget.set_annotation_box(box)

    def add_list_item(self, name, index, color: QColor, annotation_object: UAnnotationBox, scene: UAnnotationGraphicsView):
        annotation_widget = UListAnnotationItem(name, index, color, annotation_object, scene)
        item = QListWidgetItem(self)
        item.setSizeHint(annotation_widget.sizeHint())
        self.setItemWidget(item, annotation_widget)

    def on_item_clicked(self, item):
        widget = self.itemWidget(item)
        if isinstance(widget, UListAnnotationItem):
            widget.select_scene_object()

    def _update_item_indexes(self):
        for index in range(self.count()):
            widget = self.itemWidget(self.item(index))
            if not (widget and isinstance(widget, UListAnnotationItem)):
                return

            widget.set_index(index + 1)

class UListAnnotationItem(QWidget):
    def __init__(self, name, index, color: QColor, annotation_object: UAnnotationBox, scene: UAnnotationGraphicsView):
        super().__init__()

        self.annotation_object = annotation_object  # Ссылка на объект на сцене
        self.index = index
        self.name = name
        self.scene = scene

        # Создаём цветной прямоугольник (UColorLabel с фоном)
        self.color_label = UColorLabel(color)
        self.color_label.setFixedSize(30, 12)  # Размер квадрата

        # Текстовое описание
        self.text_label = QLabel(f"{index}\t {name}")
        font = QFont()
        font.setPointSize(10)
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

    def set_text(self, index: int, text: str):
        self.text_label.setText(f"{index}\t {text}")
        self.index = index
        self.name = text

    def set_name(self, name: str):
        self.name = name
        self.text_label.setText(f"{self.index}\t {self.name}")

    def set_index(self, index: int):
        self.index = index
        self.text_label.setText(f"{self.index}\t {self.name}")

    def get_name(self):
        return self.name

    def set_annotation_box(self, box: UAnnotationBox):
        self.annotation_object = box

    def set_color(self, color: QColor):
        self.color_label.update_color(color)


class UListClassCounts(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.class_items: OrderedDict[int, tuple[QListWidgetItem, UListItemClassCount]] = OrderedDict()

    def increase_class(self, class_id: int, class_name: str, color: QColor):
        if class_id in self.class_items:
            _, widget = self.class_items[class_id]
            widget.increment()
        else:
            item = QListWidgetItem()
            widget = UListItemClassCount(class_id, class_name, color)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)
            self.class_items[class_id] = item, widget

    def decrease_class(self, class_id: int):
        if class_id in self.class_items:
            item, widget = self.class_items[class_id]
            if widget.decrement():
                row = self.row(item)
                self.takeItem(row)
                del self.class_items[class_id]


class UListItemClassCount(QWidget):
    def __init__(self, class_id: int, class_name: str, color: QColor):
        super().__init__()

        self.class_id = class_id
        self.class_name = class_name
        self.count = 1

        self.color_box = UColorLabel(QColor(color))
        self.color_box.setFixedSize(20, 20)

        self.label_name = QLabel(class_name)
        self.label_count = QLabel(f"x {self.count}")

        font = QFont()
        font.setPointSize(10)
        self.label_name.setFont(font)
        self.label_count.setFont(font)
        self.label_name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self.label_name, 1)
        info_layout.addWidget(self.label_count, 0)

        info_container = QWidget()
        info_container.setLayout(info_layout)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)
        layout.addWidget(self.color_box, 0)
        layout.addWidget(info_container, 1)  # тянется

    def increment(self):
        self.count += 1
        self.label_count.setText(f"x {self.count}")

    def decrement(self):
        self.count -= 1
        self.label_count.setText(f"x {self.count}")
        return self.count <= 0