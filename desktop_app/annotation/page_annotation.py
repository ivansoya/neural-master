import os.path
from typing import Optional

from PyQt5.QtWidgets import QFileDialog, QWidget, QDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtCore import Qt, pyqtSlot

from annotation.annotation_scene import UAnnotationBox
from design.annotation_page import Ui_annotataion_page
from commander import UGlobalSignalHolder, UAnnotationSignalHolder
from annotation.carousel import UAnnotationThumbnail
from design.diag_create_dataset import Ui_diag_create_dataset
from dataset.loader import UOverlayLoader
from project import UTrainProject, UMergeAnnotationThread, DATASETS
from utility import EWorkMode, EAnnotationStatus, UMessageBox, FAnnotationData, FAnnotationItem


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
        self.commander.drop_pressed.connect(lambda: self.annotation_scene.clean_all_annotations(to_emit=True))
        self.commander.number_key_pressed.connect(self.handle_clicked_number_key)

        self.commander.arrows_pressed.connect(self.thumbnail_carousel.select_thumbnail_by_arrow)
        self.commander.drop_pressed.connect(self.thumbnail_carousel.set_thumbnail_dropped)

        self.commander.loaded_images_to_annotate.connect(self.handle_on_annotation_data_get)

        # Обработка событий при нажатии на кнопки страницы
        self.load_images_button.clicked.connect(self.handle_on_button_load_clicked)
        self.button_add_to_project.clicked.connect(self.handle_clicked_add_to_project)

        # Привязка смены класса со сценой
        self.list_class_selector.class_selected.connect(self.annotation_scene.set_annotate_class)

        # Обработка автоаннотации
        self.annotate_commander.selected_thumbnail.connect(self.handle_auto_annotate_on_select)
        self.annotate_commander.displayed_image.connect(self.handle_print_image_name)

        # Обработка события изменения режима работы
        self.annotate_commander.change_work_mode.connect(self.set_label_work_mode)
        self.select_dragmode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.DragMode.value: self.annotate_commander.change_work_mode.emit(mode)
        )
        self.select_annotatemode_button.clicked.connect(
            lambda checked=False, mode=EWorkMode.AnnotateMode.value: self.annotate_commander.change_work_mode.emit(mode)
        )

        self.annotate_commander.display_annotations.connect(self.handle_on_screen_loaded_annotations)
        self.annotate_commander.added_new_annotation.connect(self.handle_on_screen_added_annotations)
        self.annotate_commander.deleted_annotation.connect(self.handle_on_screen_deleted_annotations)
        self.annotate_commander.updated_annotation.connect(self.handle_on_screen_updated_annotations)
        self.annotate_commander.selected_annotation.connect(self.handle_on_select_annotation)

        self.annotate_commander.change_status_thumbnail.connect(self.handle_on_change_thumbnail_status)

        self.list_current_annotations.item_selected.connect(self.handle_on_select_annotation_from_list)

        # Обработка событий, связанных с работой модели
        self.commander.command_key_pressed.connect(self.handle_command_pressed)
        self.commander.model_loaded.connect(self.handle_on_load_model)

        #Обработка событий при изменении классов
        self.commander.classes_updated.connect(self.handle_on_updated_classes)

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
        self._load_classes()

    def handle_on_updated_classes(self):
        self._load_classes()

    @pyqtSlot(tuple, int)
    def handle_auto_annotate_on_select(self, thumb_tuple: tuple, status: int):
        if self.project.model_worker and self.project.model_worker.is_running():
            if self.auto_annotate_checkbox.isChecked():
                if status == EAnnotationStatus.NoAnnotation.value:
                    self._annotate_image()

    @pyqtSlot(int)
    def handle_command_pressed(self, key: int):
        if (key == Qt.Key_Space and
                self.thumbnail_carousel.get_current_thumbnail_status() != EAnnotationStatus.PerformingAnnotation and
                self.project.model_worker and self.project.model_worker.is_running()):
            self._annotate_image()

    def handle_on_load_model(self):
        self.auto_annotate_checkbox.setEnabled(True)
        if self.project.model_worker:
            self.project.model_worker.signal_on_added.connect(self.annotation_scene.handle_image_move_to_model)
            self.project.model_worker.signal_on_added.connect(self.thumbnail_carousel.handle_on_adding_thumb_to_model)

            self.project.model_worker.signal_on_result.connect(self.handle_get_results_from_model_thread)

    @pyqtSlot(list)
    def handle_on_annotation_data_get(self, annotation_data_list: list[FAnnotationItem]):
        self.list_total_annotations.clear()
        self.load_images(annotation_data_list)

    @pyqtSlot()
    def handle_on_button_load_clicked(self):
        file_paths, _ = QFileDialog.getOpenFileNames(None, "Select Images", "",
                                                     "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_paths:
            self.load_images(file_paths)
            self.list_total_annotations.clear()
        else:
            UMessageBox.show_error("Нет файлов!")

    def load_images(self, files: list[str] | list[FAnnotationItem]):
        if files is None:
            UMessageBox.show_error("Ошибка в загрузке изображений!")
            return
        # Отображение карусели
        self.thumbnail_carousel.setVisible(True)
        self.toggle_round_images.setEnabled(True)
        self.toggle_round_images.setVisible(True)

        # Очистка старого контента
        self.thumbnail_carousel.clear_thumbnails()

        # Обновление значений
        self.current_annotated_count = 0
        self.current_dropped_count = 0
        self.current_not_annotated_count = 0

        self.label_count_annotated.setText(str(self.current_annotated_count))
        self.label_count_not_annotated.setText(str(self.current_not_annotated_count))
        self.label_count_dropped.setText(str(self.current_dropped_count))

        self.load_thumbnails(files)

        self.thumbnail_carousel.update()

    @pyqtSlot()
    def handle_clicked_add_to_project(self):
        if self.overlay or (self.merge_thread and self.merge_thread.isRunning()):
            return
        list_annotations, list_nones, list_to_delete = self.thumbnail_carousel.get_annotations()
        if len(list_annotations) == 0 and len(list_nones) == 0 and len(list_to_delete) == 0:
            UMessageBox.show_error("Нет выбранных аннотаций!")
            return

        if len(list_nones) != 0:
            dialog = UTextInputDialog()
            self.commander.set_block(True)
            dialog.combo_choose_dataset.addItems(self.project.get_datasets())
            dialog.combo_choose_dataset.currentTextChanged.connect(
                lambda selected_item: dialog.lineedit_dataset_name.setText(selected_item)
            )
            if dialog.exec_():
                dataset_name = dialog.lineedit_dataset_name.text()
                for ann_item in list_nones:
                    ann_item.set_dataset_name(dataset_name)
                list_annotations.extend(list_nones)

        self.overlay = UOverlayLoader(self.display_scene)
        self.merge_thread = UMergeAnnotationThread(self.project, list_annotations, list_to_delete, DATASETS)
        self.merge_thread.signal_on_loaded_image.connect(self.overlay.update_progress)
        self.merge_thread.signal_on_ended.connect(self.handle_on_ended_adding_dataset)
        self.merge_thread.start()

        self.commander.set_block(False)

    @pyqtSlot(str)
    def handle_on_ended_adding_dataset(self, dataset_name: str):
        UMessageBox.show_ok("Добавлены аннотации в проект!")
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.project.save()
        self.thumbnail_carousel.clear_thumbnails()
        self.annotation_scene.clear()
        if self.commander:
            self.commander.go_to_page_datasets.emit()
            self.commander.project_updated_datasets.emit()

    @pyqtSlot(list)
    def handle_on_screen_loaded_annotations(self, annotations: list[tuple[int, UAnnotationBox]]):
        self.list_current_annotations.clear_list_widget()
        for index in range(len(annotations)):
            index, ann_box = annotations[index]
            self.list_current_annotations.add_item(ann_box.get_class_name(), ann_box.get_color())

    @pyqtSlot(int, object)
    def handle_on_screen_added_annotations(self, index: int, annotation_data):
        if not isinstance(annotation_data, FAnnotationData):
            return
        if index == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.add_item(
                annotation_data.get_class_name(),
                QColor(annotation_data.get_color())
            )
        self.list_total_annotations.increase_class(
            annotation_data.get_id(),
            annotation_data.get_class_name(),
            annotation_data.get_color()
        )

    @pyqtSlot(int, list)
    def handle_get_results_from_model_thread(self, index: int, result_annotations: list):
        current_annotations = self.thumbnail_carousel.get_annotation_data_by_index(index) or []
        for annotation in current_annotations:
            self.list_total_annotations.decrease_class(annotation.get_id())

        self.thumbnail_carousel.handle_on_getting_result_from_model(index, result_annotations)

        if index == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.clear_list_widget()
            self.annotation_scene.handle_get_result_from_model(result_annotations)

        for annotation in result_annotations:
            if not isinstance(annotation, FAnnotationData):
                continue

            self.list_total_annotations.increase_class(
                annotation.get_id(),
                annotation.get_class_name(),
                annotation.get_color()
            )
            if index == self.annotation_scene.get_current_thumb_index():
                self.list_current_annotations.add_item(
                    annotation.get_class_name(),
                    QColor(annotation.get_color())
                )

    @pyqtSlot(int, int, object)
    def handle_on_screen_deleted_annotations(self, index_thumb: int, index_deleted: int, deleted_data: object):
        if index_thumb == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.remove_list_item(index_deleted)
        if isinstance(deleted_data, FAnnotationData):
            self.list_total_annotations.decrease_class(deleted_data.get_id())

    @pyqtSlot(int, int, object, object)
    def handle_on_screen_updated_annotations(
            self,
            index_thumb: int,
            index_annotation: int,
            prev_annotation: FAnnotationData | None,
            updated_annotation: FAnnotationData
    ):
        if not isinstance(updated_annotation, FAnnotationData):
            return
        if index_thumb == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.update_item(
                index_annotation,
                updated_annotation.get_class_name(),
                updated_annotation.get_color()
            )
        if not isinstance(prev_annotation, FAnnotationData) or prev_annotation.get_id() == updated_annotation.get_id():
            return
        else:
            self.list_total_annotations.decrease_class(prev_annotation.get_id())
            self.list_total_annotations.increase_class(
                updated_annotation.get_id(),
                updated_annotation.get_class_name(),
                updated_annotation.get_color()
            )

    @pyqtSlot(int)
    def handle_on_select_annotation_from_list(self, index: int):
        self.annotation_scene.select_annotation_by_index(index)

    @pyqtSlot(int)
    def handle_on_select_annotation(self, index: int):
          self.list_current_annotations.select_item(index)

    @pyqtSlot(str)
    def handle_print_image_name(self, image_path: str):
        self.label_file_name.setText(os.path.basename(image_path))

    def load_thumbnails(self, files: list[str] | list[FAnnotationItem]):
        if self.overlay:
            UMessageBox.show_error("Не удалось выполнить загрузку изображений!")
            return

        self.overlay = UOverlayLoader(self)

        if len(files) == 0:
            UMessageBox.show_error("В списке нет изображений!")
            self.overlay = UOverlayLoader.delete_overlay(self.overlay)
            return

        for index in range(len(files)):
            file = files[index]
            if isinstance(file, str):
                thumb = UAnnotationThumbnail(
                    200,
                    175,
                    files[index],
                    None,
                    []
                )
            elif isinstance(file, FAnnotationItem):
                ann_data = file.get_annotation_data()
                thumb = UAnnotationThumbnail(
                    200,
                    175,
                    file.get_image_path(),
                    file.get_dataset_name(),
                    [annotation.copy() for annotation in ann_data]
                )
                for annotation in ann_data:
                    self.list_total_annotations.increase_class(
                        annotation.get_id(),
                        annotation.get_class_name(),
                        annotation.get_color()
                    )
            else:
                continue
            thumb = self.thumbnail_carousel.add_thumbnail(thumb)
            self.update_labels_by_status(thumb.annotation_status, True)
            self.label_count_images.setText(str(len(self.thumbnail_carousel.thumbnails)))
            self.overlay.update_progress(
                file.get_image_path() if isinstance(file, FAnnotationItem) else file,
                index + 1,
                len(files)
            )

        UMessageBox.show_ok("Изображения загружены!")
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.annotation_scene.center_on_selected()

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

    @pyqtSlot(EAnnotationStatus, EAnnotationStatus)
    def handle_on_change_thumbnail_status(self, prev: EAnnotationStatus, current: EAnnotationStatus):
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
        if self.project.model_worker and self.project.model_worker.is_running():
            self.project.model_worker.add_to_queue(
                thumb_id,
                matrix
            )

    def _load_classes(self):
        self.list_class_selector.clear()
        for class_id in self.project.classes.get_all_ids():
            self.list_class_selector.add_class(
                class_id,
                self.project.classes.get_name(class_id),
                self.project.classes.get_color(class_id)
            )

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