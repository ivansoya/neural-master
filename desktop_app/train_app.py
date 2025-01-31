import sys
from typing import Optional

import cv2
import os
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, \
    QWidget, QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView, QGraphicsRectItem
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QImage, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

from ultralytics import YOLO

from dataset import UDatasetDialog
from design import Ui_TrainApp
from commander import UGlobalSignalHolder
from annotable import UAnnotationBox, ImageAnnotationScene
from carousel import UAnnotationThumbnail
from utility import EWorkMode, EAnnotationStatus, FClassData, FDatasetInfo
from dataset import UDatasetCreator
from window_class_add import UAddClassWindow


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
        self.dataset_info: Optional[FDatasetInfo] = None

        self.class_list_item_model = QStandardItemModel()

        self.annotate_scene = ImageAnnotationScene(commander = self.global_signal_holder, view = self.annotate_view)
        self.thumbnail_carousel.set_commander(self.global_signal_holder)
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

        self.global_signal_holder.command_key_pressed.connect(self.annotate_on_button_pressed)

        self.button_load_dataset.clicked.connect(self.on_clicked_load_dataset)

        # Изменение label для отображения количества размеченных и неразмеченных изображений
        self.current_annotated_count: int = 0
        self.current_dropped_count: int = 0
        self.current_not_annotated_count: int = 0
        self.global_signal_holder.changed_annotation_status.connect(self.handle_changed_annotation_status)

        self.button_create_dataset.clicked.connect(self.show_dialog_create_dataset)

        # Добавление нового класса
        self.button_add_class.clicked.connect(self.on_clicked_add_class)
        self.global_signal_holder.added_new_class.connect(self.on_get_new_class)

    def load_model(self):
        model_file, _ = QFileDialog.getOpenFileName(self, "Выбрать pt модель", "",
                                                     "Image Files (*.pt)")
        if model_file:
            self.model_yolo = YOLO(model_file)

            # Инициализация ComboBox
            class_names = self.model_yolo.names

            self.class_list_item_model.clear()
            self.annotate_scene.available_classes.clear()
            self.thumbnail_carousel.available_classes.clear()
            for i in range(0, len(class_names)):
                class_t = FClassData(i, class_names[i], FClassData.get_save_color(i))
                self.annotate_scene.add_class(class_t)
                self.thumbnail_carousel.add_class(class_t)
                item_t = QStandardItem(str(class_t))
                item_t.setData(class_t, Qt.UserRole)
                self.class_list_item_model.appendRow(item_t)


            self.current_model_label.setText(os.path.basename(self.model_yolo.model_name))

            self.class_combobox.setModel(self.class_list_item_model)

            self.class_combobox.setEnabled(True)
            self.button_add_class.setEnabled(True)
            self.auto_annotate_checkbox.setEnabled(True)

        return

    def load_images(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "",
                                                     "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_paths:
            # Отображение карусели
            self.thumbnail_carousel.setVisible(True)
            self.toggle_round_images.setEnabled(True)
            self.toggle_round_images.setVisible(True)

            self.image_paths = file_paths

            # Очистка старого контента
            self.thumbnail_carousel.clear_thumbnails()

            # Обновление значений
            self.current_annotated_count = 0
            self.current_dropped_count = 0
            self.current_not_annotated_count = 0

            self.label_count_annotated.setText(str(self.current_annotated_count))
            self.label_count_not_annotated.setText(str(self.current_not_annotated_count))
            self.label_count_dropped.setText(str(self.current_dropped_count))

            self.load_thumbnails()

            self.thumbnail_carousel.update()

    def load_thumbnails(self):
        if self.image_paths:
            image_path = self.image_paths.pop(0)

            thumb = self.thumbnail_carousel.add_thumbnail(image_path)
            self.update_labels_by_status(thumb.annotation_status, True)
            self.label_count_images.setText(str(len(self.thumbnail_carousel.thumbnails)))

            QTimer.singleShot(10, lambda: self.load_thumbnails())

    def display_image(self, thumbnail: UAnnotationThumbnail):
        self.annotate_scene.clear()
        try:
            self.image_matrix = cv2.imread(thumbnail.get_image_path())
        except Exception:
            self.image_matrix = None
        if self.image_matrix is not None:
            try:
                image_t = cv2.cvtColor(self.image_matrix, cv2.COLOR_BGR2RGB)
                height, width, channel = image_t.shape
                bytes_per_line = 3 * width
                qimg = QImage(image_t.data, width, height, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
            except Exception:
                pixmap = QPixmap()

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

        else:
            self.image_on_scene = QGraphicsPixmapItem(QPixmap())

    def auto_annotate(self):
        if self.image_matrix is None or self.model_yolo is None:
            return
        if self.thumbnail_carousel.current_selected.annotation_status.value == EAnnotationStatus.Annotated.value:
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

    def on_clicked_add_class(self):
        self.global_signal_holder.set_block(True)
        id_class = self.class_combobox.count()
        window = UAddClassWindow(id_class, self.global_signal_holder)
        window.exec_()

    def on_get_new_class(self, class_data: FClassData):
        item_t = QStandardItem(str(class_data))
        item_t.setData(class_data, Qt.UserRole)
        self.class_list_item_model.appendRow(item_t)
        self.class_combobox.update()

    def on_clicked_load_dataset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите YAML файл",
            "",
            "Файлы датасетов (*.yaml *.txt);;Все файлы (*)",
            options=QFileDialog.Options()
        )
        if file_path:
            try:
                self.dataset_info = FDatasetInfo(file_path)
                self.button_create_dataset.setText("Добавить в датасет")
            except Exception as e:
                self.dataset_info = None
                print(f"Ошибка {repr(e)}")

    def annotate_on_button_pressed(self, key: int):
        if key == Qt.Key_Space:
            self.auto_annotate()

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

    def increment_current_annotated(self, is_increase: bool):
        if is_increase:
            self.current_annotated_count += 1
        else:
            self.current_annotated_count -= 1
        return self.current_annotated_count

    def show_dialog_create_dataset(self):
        if len(self.annotate_scene.available_classes) <= 0 or len(self.thumbnail_carousel.thumbnails) <= 0:
            return
        if self.dataset_info is None:
            dialog = UDatasetDialog(
                self.annotate_scene.available_classes,
                self.thumbnail_carousel.thumbnails
            )
            dialog.exec_()
        else:
            dialog = UDatasetDialog(
                self.annotate_scene.available_classes,
                self.thumbnail_carousel.thumbnails,
                self.dataset_info
            )
            dialog.label_dataset_path.setText(self.dataset_info.datafile_path)
            dialog.button_choose_path_dataset.setEnabled(False)
            dialog.combo_dataset_type.setCurrentIndex(self.dataset_info.get_type_index())
            dialog.combo_dataset_type.setEnabled(False)
            dialog.exec_()

    def handle_changed_annotation_status(self, prev: EAnnotationStatus, current: EAnnotationStatus):
        self.update_labels_by_status(prev, False)
        self.update_labels_by_status(current, True)

    def update_labels_by_status(self, status: EAnnotationStatus, to_increase: bool):
        value = 1 if to_increase is True else -1
        if status.value == EAnnotationStatus.Annotated.value:
            self.current_annotated_count += value
            self.label_count_annotated.setText(str(self.current_annotated_count))
        elif status.value == EAnnotationStatus.NoAnnotation.value:
            self.current_not_annotated_count += value
            self.label_count_not_annotated.setText(str(self.current_not_annotated_count))
        elif status.value == EAnnotationStatus.MarkedDrop.value:
            self.current_dropped_count += value
            self.label_count_dropped.setText(str(self.current_dropped_count))

def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
