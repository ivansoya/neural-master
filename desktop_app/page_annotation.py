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
from project import UTrainProject, UMergeAnnotationThread, DATASETS
from utility import EWorkMode, EAnnotationStatus, FDatasetInfo, UMessageBox, FAnnotationData


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
        self.merge_thread: Optional[UMergeAnnotationThread] = None

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

        # Обработка событий при нажатии на кнопки страницы
        self.load_images_button.clicked.connect(self.load_images)
        self.button_add_to_project.clicked.connect(self.handle_clicked_add_to_project)

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

        # Обработка событий, связанных с работой модели
        self.commander.command_key_pressed.connect(self.handle_command_pressed)
        self.commander.model_loaded.connect(self.handle_on_load_model)

        #self.commander.changed_class_annotate.connect(self.on_change_index_combobox)
        #self.class_combobox.currentIndexChanged.connect(self.handle_changed_class_combobox_index)

        #self.thumbnail_carousel.signal_thumbnail_select.connect(self.display_image)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

        #self.commander.command_key_pressed.connect(self.annotate_on_button_pressed)

        # self.button_load_dataset.clicked.connect(self.on_clicked_load_dataset)

        # Изменение label для отображения количества размеченных и неразмеченных изображений
        #self.commander.changed_annotation_status.connect(self.handle_changed_annotation_status)

    def handle_on_load_project(self):
        if self.project is None:
            return
        for class_id in self.project.classes.get_all_ids():
            self.list_class_selector.add_class(
                class_id,
                self.project.classes.get_name(class_id),
                self.project.classes.get_color(class_id)
            )

    def handle_command_pressed(self, key: int):
        if key == int(Qt.Key_Space):
            self.annotation_scene.clean_all_annotations(0)
            self._annotate_image()
            pass

    def handle_on_load_model(self):
        self.auto_annotate_checkbox.setEnabled(True)
        if self.project.model_thread:
            self.project.model_thread.signal_on_added.connect(self.annotation_scene.handle_image_move_to_model)
            self.project.model_thread.signal_on_added.connect(self.thumbnail_carousel.handle_on_adding_thumb_to_model)
            self.project.model_thread.signal_on_result.connect(self.annotation_scene.handle_get_result_from_model)
            self.project.model_thread.signal_on_result.connect(self.thumbnail_carousel.handle_on_getting_result_from_model)

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

    def handle_clicked_add_to_project(self):
        if self.overlay or (self.merge_thread and self.merge_thread.isRunning()):
            return
        dict_dataset, list_annotations = self.thumbnail_carousel.get_annotations()

        if len(list_annotations) == 0 and len(dict_dataset) == 0:
            return
        dialog = UTextInputDialog()
        self.commander.set_block(True)
        if dialog.exec_():
            dataset_name = dialog.lineedit_dataset_name.text()
            if dataset_name not in dict_dataset:
                dict_dataset[dataset_name] = list_annotations
            else:
                dict_dataset[dataset_name] += list_annotations

            self.overlay = UOverlayLoader(self.display_scene)
            self.merge_thread = UMergeAnnotationThread(self.project, dict_dataset, DATASETS)

            self.merge_thread.signal_on_loaded_image.connect(self.overlay.update_progress)
            self.merge_thread.signal_on_ended.connect(self.handle_on_ended_adding_dataset)

            self.merge_thread.start()

        self.commander.set_block(False)

    def handle_on_ended_adding_dataset(self, dataset_name: str):
        UMessageBox.show_error("Добавлены аннотации в проект!", "Успех!", int(QMessageBox.Ok))
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.project.save()
        self.commander.project_updated_datasets.emit()
        return

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

    def on_get_new_class(self, class_data: str):
        item_t = QStandardItem(str(class_data))
        item_t.setData(class_data, Qt.UserRole)
        self.class_list_item_model.appendRow(item_t)
        self.class_combobox.update()

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

    def _annotate_image(self):
        thumb_id, matrix = self.annotation_scene.get_selectable_matrix()
        if thumb_id is None or matrix is None:
            return
        if self.project.model_thread and self.project.model_thread.is_running():
            self.project.model_thread.add_to_queue(thumb_id, matrix)

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