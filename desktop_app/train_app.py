import sys

import cv2
import os
from functools import partial
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, \
    QWidget, QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView, QGraphicsRectItem
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QImage, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer

from ultralytics import YOLO

from design import Ui_TrainApp
from commander import UGlobalSignalHolder
from carousel import UThumbnailCarousel
from annotable import UAnnotationBox, ImageAnnotationScene, UAnnotationGraphicsView
from desktop_app.carousel import UAnnotationThumbnail
from desktop_app.utility import EWorkMode, EAnnotationStatus
from utility import GColorList, FClassData
from custom_widgets import UHorizontalScrollArea

class TrainApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.global_signal_holder = UGlobalSignalHolder()
        QApplication.instance().installEventFilter(self.global_signal_holder)

        self.image_paths = []
        self.image_on_scene = None
        self.image_matrix = None

        self.model_yolo = None

        self.class_list_item_model = QStandardItemModel()

        self.annotate_scene = ImageAnnotationScene(commander = self.global_signal_holder)
        self.annotate_view.setScene(self.annotate_scene)

        self.global_signal_holder.ctrl_pressed.connect(self.annotate_view.enable_drag_mode)
        self.global_signal_holder.ctrl_released.connect(self.annotate_view.disable_drag_mode)
        self.global_signal_holder.delete_pressed.connect(self.annotate_scene.delete_on_press_key)
        self.global_signal_holder.drop_pressed.connect(self.annotate_scene.clean_all_annotations)

        self.toggle_round_images.setVisible(False)
        self.thumbnail_carousel.setVisible(False)

        self.global_signal_holder.arrows_pressed.connect(self.thumbnail_carousel.select_thumbnail_by_arrow)
        self.global_signal_holder.drop_pressed.connect(self.thumbnail_carousel.set_thumbnail_dropped)

        self.global_signal_holder.added_new_annotation.connect(self.thumbnail_carousel.handle_signal_on_added_annotation)
        self.global_signal_holder.updated_annotation.connect(self.thumbnail_carousel.handle_signal_on_update_annotation)
        self.global_signal_holder.deleted_annotation.connect(self.thumbnail_carousel.handle_signal_on_delete_annotation)

        self.load_images_button.clicked.connect(self.load_images)
        self.load_model_button.clicked.connect(self.load_model)

        self.global_signal_holder.change_work_mode.connect(self.set_label_work_mode)
        self.select_dragmode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.DragMode.value: self.global_signal_holder.change_work_mode.emit(mode)
        )
        self.select_annotatemode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.AnnotateMode.value: self.global_signal_holder.change_work_mode.emit(mode)
        )

        self.global_signal_holder.changed_class_annotate.connect(self.on_change_index_combobox)
        self.class_combobox.currentIndexChanged.connect(self.handle_changed_class_combobox_index)

        self.thumbnail_carousel.signal_thumbnail_select.connect(self.display_image)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

    def load_model(self):
        model_file, _ = QFileDialog.getOpenFileName(self, "Выбрать pt модель", "",
                                                     "Image Files (*.pt)")
        if model_file:
            self.model_yolo = YOLO(model_file)

            # Инициализация ComboBox
            class_names = self.model_yolo.names

            self.class_list_item_model.clear()
            self.annotate_scene.available_classes.clear()
            for i in range(0, len(class_names)):
                class_t = FClassData(i, class_names[i], FClassData.get_save_color(i))
                self.annotate_scene.add_class(class_t)
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
            self.thumbnail_carousel.clear_thumbnails()

            # Отображение карусели
            self.thumbnail_carousel.setVisible(True)
            self.toggle_round_images.setEnabled(True)
            self.toggle_round_images.setVisible(True)

            self.load_thumbnails()

    def load_thumbnails(self):
        if self.image_paths:
            image_path = self.image_paths.pop(0)

            self.thumbnail_carousel.add_thumbnail(image_path)

            QTimer.singleShot(50, lambda: self.load_thumbnails())

    def display_image(self, thumbnail: UAnnotationThumbnail):
        self.annotate_scene.clear()
        self.image_matrix = cv2.imread(thumbnail.get_image_path())
        if self.image_matrix is not None:
            image_t = cv2.cvtColor(self.image_matrix, cv2.COLOR_BGR2RGB)
            height, width, channel = image_t.shape
            bytes_per_line = 3 * width
            qimg = QImage(image_t.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.image_on_scene = QGraphicsPixmapItem(pixmap)
            self.annotate_scene.addItem(self.image_on_scene)
            self.annotate_scene.image = self.image_on_scene
            self.image_on_scene.setPos(16000 - self.image_on_scene.boundingRect().width() // 2,
                                       16000 - self.image_on_scene.boundingRect().height() // 2)

            if (self.auto_annotate_checkbox.isChecked() and
                thumbnail.annotation_status.value == EAnnotationStatus.NoAnnotation.value):
                self.auto_annotate()
            elif thumbnail.annotation_status.value == EAnnotationStatus.Annotated.value:
                class_indexes = [index for index in range(self.class_combobox.count())]
                for ann_data in thumbnail.annotation_data_list:
                    if ann_data.ClassID not in class_indexes:
                        continue
                    self.annotate_scene.add_annotation_box(
                        ann_data.X,
                        ann_data.Y,
                        ann_data.Width,
                        ann_data.Height,
                        self.class_combobox.itemData(ann_data.ClassID),
                        False
                    )
            elif thumbnail.annotation_status.value == EAnnotationStatus.MarkedDrop.value:
                pass

            print("Количество боксов на сцене: ", len(self.annotate_scene.boxes_on_scene))

    def auto_annotate(self):
        if self.image_matrix is None or self.model_yolo is None:
            return

        result = self.model_yolo.predict(self.image_matrix, imgsz=(640, 640))[0]

        conf_list = result.boxes.conf.cpu().tolist()
        boxes = result.boxes.xyxy.cpu().tolist()
        d_classes = result.boxes.cls.cpu().tolist()

        for box, d_class, conf in zip(boxes, d_classes, conf_list):
            label_conf = round(conf, 1)
            print(int(d_class), *box, label_conf)

            self.annotate_scene.add_annotation_box(
                box[0],
                box[1],
                box[2] - box[0],
                box[3] - box[1],
                self.class_combobox.itemData(int(d_class))
            )

    def set_label_work_mode(self, mode: int):
        self.selected_label.setText(str(mode))

    def handle_changed_class_combobox_index(self, index):
        self.global_signal_holder.changed_class_annotate.emit(index)

    def on_change_index_combobox(self, index):
        if self.class_combobox.currentIndex() != index:
            self.class_combobox.setCurrentIndex(index)

    def toggle_roulette_visibility(self):
        if self.thumbnail_carousel.isVisible():
            self.thumbnail_carousel.setVisible(False)
            self.toggle_round_images.setText("Показать карусель")
        else:
            self.thumbnail_carousel.setVisible(True)
            self.toggle_round_images.setText("Скрыть карусель")

def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
