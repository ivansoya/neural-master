import sys
from symtable import Class

import cv2
import os
from functools import partial
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, \
    QWidget, QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView, QGraphicsRectItem
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QImage, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer
from sympy.physics.units import current

from ultralytics import YOLO

from design import Ui_TrainApp
from annotable import UAnnotationBox, ImageAnnotationScene, UAnnotableGraphicsView
from desktop_app.utility import EWorkMode
from utility import GColorList, FClassData
from custom_widgets import UHorizontalScrollArea

class TrainApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.image_paths = []
        self.image_thumbnails = []
        self.image_on_scene = None
        self.image_matrix = None
        self.thumbnail_size = 150
        self.selected_size = 200
        self.selected_thumbnail = None

        self.model_yolo = None

        self.class_list_item_model = QStandardItemModel()

        self.graphics_scene = ImageAnnotationScene()
        self.image_view.setScene(self.graphics_scene)

        self.toggle_round_images.setVisible(False)
        self.round_images.setVisible(False)

        self.load_images_button.clicked.connect(self.load_images)
        self.load_model_button.clicked.connect(self.load_model)

        self.select_dragmode_button.clicked.connect(partial(self.handle_click_select_mode, EWorkMode.DragMode))
        self.select_annotatemode_button.clicked.connect(partial(self.handle_click_select_mode, EWorkMode.AnnotateMode))

        self.class_combobox.currentIndexChanged.connect(self.on_selection_class_change)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

    def load_model(self):
        model_file, _ = QFileDialog.getOpenFileName(self, "Выбрать pt модель", "",
                                                     "Image Files (*.pt)")
        if model_file:
            self.model_yolo = YOLO(model_file)

            # Инициализация ComboBox
            class_names = self.model_yolo.names

            self.class_list_item_model.clear()

            for i in range(0, len(class_names)):
                class_t = FClassData(i, class_names[i], FClassData.get_save_color(i))
                item_t = QStandardItem(str(class_t))
                item_t.setData(class_t, Qt.UserRole)
                self.class_list_item_model.appendRow(item_t)

            self.current_model_label.setText(os.path.basename(self.model_yolo.model_name))

            self.class_combobox.setModel(self.class_list_item_model)

            self.class_combobox.setEnabled(True)
            self.add_class_button.setEnabled(True)
            self.auto_annotate_checkbox.setEnabled(True)

        return

    def load_images(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "",
                                                     "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_paths:
            self.image_paths = file_paths

            # Очистка старого контента
            for thumb in self.image_thumbnails:
                thumb.deleteLater()
            self.image_thumbnails.clear()

            layout = self.scroll_content.layout()
            if layout is None:
                layout = QHBoxLayout(self.scroll_content)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(10)
            else:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

            self.round_images.setVisible(True)
            self.toggle_round_images.setEnabled(True)
            self.toggle_round_images.setVisible(True)

            self.load_thumbnails(layout)

    def load_thumbnails(self, layout):
        if self.image_paths:
            image_path = self.image_paths.pop(0)

            thumb_label = QLabel()
            thumb_label.setStyleSheet("background-color: lightgray;")
            thumb_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_path)
            thumb_label.setPixmap(pixmap.scaledToHeight(
                self.thumbnail_size, Qt.SmoothTransformation
            ))
            thumb_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)

            thumb_label.mousePressEvent = lambda event, path=image_path: self.thumb_lambda_body(thumb_label, path)

            layout.addWidget(thumb_label)
            self.image_thumbnails.append(thumb_label)

            if layout.count() == 1:
                self.thumb_lambda_body(thumb_label, image_path)
                #self.fit_image_to_view()

            QTimer.singleShot(50, lambda: self.load_thumbnails(layout))

    def select_active_thumbnail(self, thumbnail):
        if self.selected_thumbnail is not None:
            self.selected_thumbnail.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        if thumbnail is not None:
            thumbnail.setFixedSize(self.selected_size, self.selected_size)
            self.selected_thumbnail = thumbnail

            # Прокручиваем область, чтобы выбранная миниатюра была в центре
            scroll_area_width = self.round_images.width()
            scroll_content_width = self.scroll_content.layout().count() * (self.thumbnail_size + 10)
            selected_index = self.image_thumbnails.index(thumbnail)
            scroll_position = max(0, selected_index * (self.thumbnail_size + 10) - scroll_area_width // 2 + self.thumbnail_size // 2)
            self.round_images.horizontalScrollBar().setValue(scroll_position)

    def display_image(self, image_path):
        # Загрузка
        self.image_matrix = cv2.imread(image_path)
        if self.image_matrix is not None:
            # Convert to RGB for displaying in QLabel
            image_t = cv2.cvtColor(self.image_matrix, cv2.COLOR_BGR2RGB)
            height, width, channel = image_t.shape
            bytes_per_line = 3 * width
            qimg = QImage(image_t.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.image_on_scene = QGraphicsPixmapItem(pixmap)
            self.graphics_scene.clear()
            self.graphics_scene.addItem(self.image_on_scene)
            self.image_on_scene.setPos(16000 - self.image_on_scene.boundingRect().width() // 2,
                                       16000 - self.image_on_scene.boundingRect().height() // 2)

            self.auto_annotate()

    def auto_annotate(self):
        if self.image_matrix is None or self.model_yolo is None or self.auto_annotate_checkbox.isChecked() is False:
            return

        result = self.model_yolo.predict(self.image_matrix, imgsz=640)[0]

        conf_list = result.boxes.conf.cpu().tolist()
        boxes = result.boxes.xyxy.cpu().tolist()
        d_classes = result.boxes.cls.cpu().tolist()

        for box, d_class, conf in zip(boxes, d_classes, conf_list):
            label_conf = round(conf, 1)
            print(int(d_class), *box, label_conf)

            ann_box = UAnnotationBox(
                box[0],
                box[1],
                box[2],
                box[3],
                self.class_combobox.itemData(int(d_class)),
                self.image_on_scene
            )

            #ann_box = ResizableRect(box[0], box[1], box[2], box[3], self.class_combobox.itemData(int(d_class)))
            #self.image_on_scene.addItem(ann_box)


    def handle_click_select_mode(self, mode):
        self.graphics_scene.setAnnotationMode(mode)
        self.selected_label.setText(str(mode.value))

    def on_selection_class_change(self, index):
        self.graphics_scene.setRectTypeDraw(self.class_combobox.itemData(index))

        current_text = str(self.class_combobox.itemData(index))
        print(f"Выбран элемент для разметки {current_text}")

    def toggle_roulette_visibility(self):
        if self.round_images.isVisible():
            self.round_images.setVisible(False)
            self.toggle_round_images.setText("Показать карусель")
        else:
            self.round_images.setVisible(True)
            self.toggle_round_images.setText("Скрыть карусель")

    def fit_image_to_view(self):
        if self.image_on_scene:
            rect = self.image_on_scene.boundingRect()
            self.image_view.fitInView(rect, Qt.KeepAspectRatio)

    def thumb_lambda_body(self, thumbnail, image_path):
        self.select_active_thumbnail(thumbnail)
        self.display_image(image_path)

def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
