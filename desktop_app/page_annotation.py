from typing import Optional

import cv2
import os
from PyQt5.QtWidgets import QFileDialog, QWidget, QGraphicsPixmapItem, QStackedWidget, QMessageBox, QDialog
from PyQt5.QtGui import QImage, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer

from dataset import UDatasetDialog
from design.annotation_page import Ui_annotataion_page
from commander import UGlobalSignalHolder, UAnnotationSignalHolder
from annotation.carousel import UAnnotationThumbnail
from design.diag_create_dataset import Ui_diag_create_dataset
from loader import UOverlayLoader
from project import UTrainProject
from utility import EWorkMode, EAnnotationStatus, FDatasetInfo, UMessageBox

class UTextInputDialog(QDialog, Ui_diag_create_dataset):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # Подключаем кнопку к обработчику
        self.button_ok.clicked.connect(self.accept)

    def get_text(self):
        """Возвращает текст, введенный в поле ввода"""
        return self.lineedit_dataset_name.text()


class UPageAnnotation(QWidget, Ui_annotataion_page):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.toggle_round_images.setVisible(False)
        self.thumbnail_carousel.setVisible(False)

        self.image_paths = []
        self.image_on_scene = None
        self.image_matrix = None

        self.model_yolo = None
        self.dataset_info: Optional[FDatasetInfo] = None

        self.class_list_item_model = QStandardItemModel()

        self.commander = commander
        self.project = project

        # Обработчик событий для сцены разметки
        self.annotate_commander = UAnnotationSignalHolder()
        self.thumbnail_carousel.set_commander(self.annotate_commander)
        self.annotation_scene.set_commander(self.annotate_commander)

        # Инициализация потоков
        self.overlay: Optional[UOverlayLoader] = None

        self.current_annotated_count: int = 0
        self.current_dropped_count: int = 0
        self.current_not_annotated_count: int = 0

        self.commander.project_load_complete.connect(self.handle_on_load_project)

        # Сигналы событий при нажатии на клавиши
        self.commander.ctrl_pressed.connect(self.annotation_scene.handle_drag_start_event)
        self.commander.ctrl_released.connect(self.annotation_scene.handle_drag_end_event)
        self.commander.delete_pressed.connect(self.annotation_scene.delete_on_press_key)
        self.commander.drop_pressed.connect(self.annotation_scene.clean_all_annotations)
        self.commander.number_key_pressed.connect(self.handle_clicked_number_key)

        self.commander.arrows_pressed.connect(self.thumbnail_carousel.select_thumbnail_by_arrow)
        self.commander.drop_pressed.connect(self.thumbnail_carousel.set_thumbnail_dropped)

        self.load_images_button.clicked.connect(self.load_images)

        self.button_create_dataset.clicked.connect(self.handle_clicked_create_dataset)

        # Привязка смены класса со сценой
        self.list_class_selector.class_selected.connect(self.annotation_scene.set_annotate_class)

        # Обработка события изменения режима работы
        self.annotate_commander.change_work_mode.connect(self.set_label_work_mode)
        self.select_dragmode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.DragMode.value: self.annotate_commander.change_work_mode.emit(mode)
        )
        self.select_annotatemode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.AnnotateMode.value: self.annotate_commander.change_work_mode.emit(mode)
        )

        #self.commander.changed_class_annotate.connect(self.on_change_index_combobox)
        #self.class_combobox.currentIndexChanged.connect(self.handle_changed_class_combobox_index)

        #self.thumbnail_carousel.signal_thumbnail_select.connect(self.display_image)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

        #self.commander.command_key_pressed.connect(self.annotate_on_button_pressed)

        # self.button_load_dataset.clicked.connect(self.on_clicked_load_dataset)

        # Изменение label для отображения количества размеченных и неразмеченных изображений
        #self.commander.changed_annotation_status.connect(self.handle_changed_annotation_status)

        # Инициализация переходов по страницам
        self.button_to_datasets_settings.clicked.connect(lambda: self.go_to_another_page(1))
        self.button_to_statistics.clicked.connect(lambda: self.go_to_another_page(3))

    def handle_on_load_project(self):
        if self.project is None:
            return
        for class_id in self.project.classes.get_all_ids():
            self.list_class_selector.add_class(
                class_id,
                self.project.classes.get_name(class_id),
                self.project.classes.get_color(class_id)
            )

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

    def handle_clicked_create_dataset(self):
        dict_dataset, list_annotations = self.thumbnail_carousel.get_annotations()

        if len(list_annotations) == 0:
            return
        dialog = UTextInputDialog()
        if dialog.exec_():
            dataset_name = dialog.get_text()
            if not dataset_name in self.project.datasets:
                self.project.get_current_annotations()[dataset_name] = list_annotations
            else:

        pass

    def load_thumbnails(self):
        if self.overlay:
            UMessageBox.show_error("Не удалось выполнить загрузку изображений!")
            return

        self.overlay = UOverlayLoader(self)

        if not self.image_paths or len(self.image_paths) == 0:
            UMessageBox.show_error("Не удалось выполнить загрузку изображений!")
            self.overlay = UOverlayLoader.delete_overlay(self.overlay)
            return

        for index in range(len(self.image_paths)):
            thumb = UAnnotationThumbnail(
                200,
                175,
                self.image_paths[index],
                None,
                []
            )
            thumb = self.thumbnail_carousel.add_thumbnail(thumb)
            self.update_labels_by_status(thumb.annotation_status, True)
            self.label_count_images.setText(str(len(self.thumbnail_carousel.thumbnails)))
            self.overlay.update_progress(self.image_paths[index], index + 1, len(self.image_paths))

        UMessageBox.show_error("Изображения загружены!", "Успех", int(QMessageBox.Ok))
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)

    """def display_image(self, thumbnail: UAnnotationThumbnail):
        self.annotate_scene.clear()
        try:
            self.image_matrix = cv2.imread(thumbnail.get_image_path())
        except Exception as e:
            self.image_matrix = None
            print(f"Ошибка: {str(e)}")
        if self.image_matrix is not None:
            try:
                image_t = cv2.cvtColor(self.image_matrix, cv2.COLOR_BGR2RGB)
                height, width, channel = image_t.shape
                bytes_per_line = 3 * width
                qimg = QImage(image_t.data, width, height, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
            except Exception as e:
                pixmap = QPixmap()
                print(f"Ошибка: {str(e)}")

            self.image_on_scene = QGraphicsPixmapItem(pixmap)
            self.annotate_scene.addItem(self.image_on_scene)
            self.annotate_scene.current_image = self.image_on_scene
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
            self.image_on_scene = QGraphicsPixmapItem(QPixmap())"""

    """def auto_annotate(self):
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
            )"""

    def on_get_new_class(self, class_data: str):
        item_t = QStandardItem(str(class_data))
        item_t.setData(class_data, Qt.UserRole)
        self.class_list_item_model.appendRow(item_t)
        self.class_combobox.update()

    def annotate_on_button_pressed(self, key: int):
        if key == Qt.Key_Space:
            #self.auto_annotate()
            pass

    def set_label_work_mode(self, mode: int):
        self.selected_label.setText(str(mode))

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

    def handle_clicked_number_key(self, key_number: int):
        if key_number == int(Qt.Key_1):
            self.annotate_commander.change_work_mode.emit(EWorkMode.DragMode.value)
        elif key_number == int(Qt.Key_2):
            self.annotate_commander.change_work_mode.emit(EWorkMode.AnnotateMode.value)

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

    def go_to_another_page(self, page_index: int):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(page_index)

    """    def contextMenuEvent(self, event):
            if len(self.available_classes) == 0 or self.commander is None:
                return

            menu = QMenu()
            for class_d in self.available_classes:
                action = UAnnotationScene.set_action(
                    menu,
                    str(class_d),
                    class_d.Color
                )
                action.triggered.connect(
                    lambda checked=False, index=class_d.Cid: self.commander.changed_class_annotate.emit(index)
                )
                menu.addAction(action)

            menu.exec_(event.screenPos())"""

    """def load_model(self):
        model_file, _ = QFileDialog.getOpenFileName(self, "Выбрать модель", "",
                                                     "CNN Files (*.pt *.onnx)")
        if model_file:
            self.model_yolo = YOLO(model_file)

            # Инициализация ComboBox
            class_names = self.model_yolo.names

            self.class_list_item_model.clear()
            self.annotate_scene.available_classes.clear()
            self.thumbnail_carousel.available_classes.clear()
            for i in range(0, len(class_names)):
                self.annotate_scene.add_class(class_names[i])
                self.thumbnail_carousel.add_class(class_names[i])
                item_t = QStandardItem(str(class_names[i]))
                item_t.setData(class_names[i], Qt.UserRole)
                self.class_list_item_model.appendRow(item_t)


            self.current_model_label.setText(os.path.basename(self.model_yolo.model_name))

            self.class_combobox.setModel(self.class_list_item_model)

            self.class_combobox.setEnabled(True)
            self.button_add_class.setEnabled(True)
            self.auto_annotate_checkbox.setEnabled(True)

        return"""
