import os.path
from typing import Optional

from PyQt5.QtWidgets import QFileDialog, QWidget, QDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtCore import Qt, pyqtSlot, QTimer

import imageio.v3 as iio

from annotation.annotation_item import UAnnotationItem
from annotation.modes.abstract import EWorkMode
from annotation.annotation_scene import UAnnotationBox
from coco.coco_json import make_dump_annotations_from_coco, make_coco_json, save_coco_json
from coco.coco_project import UCocoProject
from design.annotation_page import Ui_annotataion_page
from commander import UGlobalSignalHolder, UAnnotationSignalHolder
from annotation.carousel import UAnnotationThumbnail
from design.diag_create_dataset import Ui_diag_create_dataset
from supporting.overlay_widget import UOverlayLoader
from project import UTrainProject, UMergeAnnotationThread, DATASETS
from utility import EAnnotationStatus, UMessageBox, FAnnotationData, FAnnotationItem, ECommanderStatus


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
    def __init__(self, commander: UGlobalSignalHolder, project: UCocoProject):
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

        # Инициализация потоков
        self.overlay: Optional[UOverlayLoader] = None
        self.merge_thread: Optional[UMergeAnnotationThread] = None

        self.current_annotated_count: int = 0
        self.current_dropped_count: int = 0
        self.current_not_annotated_count: int = 0

        self.commander.project_load_complete.connect(self.handle_on_load_project)

        # Привязка событий нажатий клавиш к сцене
        self.commander.key_pressed.connect(self.annotation_scene.handle_on_key_press)
        self.commander.key_hold.connect(self.annotation_scene.handle_on_key_hold)
        self.commander.key_released.connect(self.annotation_scene.handle_on_key_release)

        # Привязка событий нажатий клавиш к странице
        self.commander.key_pressed.connect(self.handle_on_key_pressed)
        self.commander.key_hold.connect(self.handle_on_key_hold)
        self.commander.key_released.connect(self.handle_on_key_released)

        self.commander.loaded_images_to_annotate.connect(self.handle_on_annotation_data_get)

        # Обработка событий при нажатии на кнопки страницы
        self.load_images_button.clicked.connect(self.handle_on_button_load_clicked)
        self.button_add_to_project.clicked.connect(self.handle_clicked_add_to_project)

        # Привязка смены класса со сценой
        self.list_class_selector.class_selected.connect(self.annotation_scene.set_annotate_class)

        # Обработка автоаннотации
        self.annotate_commander.selected_thumbnail.connect(self.handle_on_select_thumbnail)
        self.annotate_commander.displayed_image.connect(self.handle_print_image_name)

        # Обработка события изменения режима работы
        self.annotate_commander.change_work_mode.connect(self.set_label_work_mode)
        self.button_drag_mode.clicked.connect(
            lambda checked=False, mode=EWorkMode.Viewer.value: self.annotate_commander.change_work_mode.emit(mode)
        )
        self.button_detect_mode.clicked.connect(
            lambda checked=False, mode=EWorkMode.BoxAnnotationMode.value: self.annotate_commander.change_work_mode.emit(
                mode)
        )
        self.button_mask_mode.clicked.connect(
            lambda checked=False,
                   mode=EWorkMode.MaskAnnotationMode.value: self.annotate_commander.change_work_mode.emit(mode)
        )
        self.button_sam2.clicked.connect(
            lambda checked=False, mode=EWorkMode.SAM2.value: self.annotate_commander.change_work_mode.emit(mode)
        )

        self.annotate_commander.display_annotations.connect(self.handle_on_screen_loaded_annotations)
        self.annotate_commander.added_new_annotation.connect(self.handle_on_screen_added_annotations)
        self.annotate_commander.deleted_annotation.connect(self.handle_on_screen_deleted_annotations)
        self.annotate_commander.updated_annotation.connect(self.handle_on_screen_updated_annotations)
        self.annotate_commander.selected_annotation.connect(self.handle_on_select_annotation)

        self.annotate_commander.change_status_thumbnail.connect(self.handle_on_change_thumbnail_status)

        self.list_current_annotations.item_selected.connect(self.handle_on_select_annotation_from_list)

        # Обработка событий, связанных с работой модели
        self.commander.model_loaded.connect(self.handle_on_load_model)

        #Обработка событий при изменении классов
        self.commander.classes_updated.connect(self.handle_on_updated_classes)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

        # Таймер автосохранения
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(60000)
        self.autosave_timer.timeout.connect(self.on_autosave_timer_tick)

    def on_autosave_timer_tick(self):
        if not self.commander or not self.commander.get_status() is ECommanderStatus.Annotation:
            return

        self.autosave_timer.stop()
        self.try_run_task()

    def try_run_task(self):
        if self.thumbnail_carousel.get_thumbnails_count() == 0:
            self.autosave_timer.stop()
            return

        task = [
            (self.dump_task, (), {}),
        ]

        if self.project.start_task_thread(task, [self.handle_on_ended_autosave], []):
            self.commander.task_start.emit("Идет автосохранение!")

    def dump_task(self):
        result = self.thumbnail_carousel.get_dump_annotations()
        if len(result) == 0:
            self.commander.task_error.emit("Ошибка при автосохранении! (Длина 0)")
            return

        dump_coco = make_coco_json(
            result,
            self.project.annotation_classes,
            {
                'name': self.project.project_info.name,
                'description': self.project.project_info.description,
                'author': self.project.project_info.author,
                'year': self.project.project_info.year,
            },
            self.project.project_info.licenses,
            True
        )

        save_coco_json(self.project.get_project_ann_dump_path(), dump_coco)

    @pyqtSlot()
    def handle_on_ended_autosave(self):
        if not self.autosave_timer.isActive():
            self.autosave_timer.start()
        self.commander.task_finished.emit("Автосохранение завершено!")

    def handle_on_load_project(self):
        if self.project is None:
            return
        self._load_classes()
        self.thumbnail_carousel.set_commander(self.annotate_commander)
        self.annotation_scene.set_scene_parameters(self.annotate_commander, self.project.sam2_worker)

    def handle_on_updated_classes(self):
        self._load_classes()

    @pyqtSlot(tuple, int)
    def handle_on_select_thumbnail(self, thumb_tuple: tuple, status: int):
        index, name, data = thumb_tuple
        self.label_current_index.setText(str(index + 1))

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

        self.annotation_scene.set_annotation_id(self.project.get_annotation_id())
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
            dialog.combo_choose_dataset.addItems(self.project.get_annotations().keys())
            dialog.combo_choose_dataset.currentTextChanged.connect(
                lambda selected_item: dialog.lineedit_dataset_name.setText(selected_item)
            )
            if dialog.exec_() != QDialog.Accepted:
                self.commander.set_block(False)
                return

            dataset_name = dialog.get_text().strip()
            if not dataset_name:
                self.commander.set_block(False)
                return

            for ann_item in list_nones:
                ann_item.set_dataset_name(dataset_name)
                ann_item.set_image_id(self.project.get_image_id_with_increment())
            list_annotations.extend(list_nones)

        self.overlay = UOverlayLoader(self.display_scene)

        tasks = [
            (self.project.update_annotations, (list_annotations, "noname_dataset",), {}),
            (self.project.remove_list_of_annotations, (list_to_delete,), {}),
            (self.project.save, (), {}),
        ]

        self.project.start_task_thread(tasks, [self.handle_on_ended_adding_dataset], [])

        self.commander.set_block(False)

    @pyqtSlot()
    def handle_on_ended_adding_dataset(self):
        UMessageBox.show_ok("Изменение завершено!")
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.thumbnail_carousel.clear_thumbnails_to_last_annotated()
        self.annotation_scene.clear()
        self.try_run_task()
        if self.commander:
            self.commander.project_updated.emit()
            if self.thumbnail_carousel.get_thumbnails_count() == 0:
                self.commander.go_to_page_datasets.emit()
                self.autosave_timer.stop()
            else:
                self.autosave_timer.stop()
                self.autosave_timer.start()

    @pyqtSlot(list)
    def handle_on_screen_loaded_annotations(self, annotations: list[tuple[int, UAnnotationItem]]):
        self.list_current_annotations.clear_annotations()
        for index in range(len(annotations)):
            index, ann_item = annotations[index]
            self.list_current_annotations.add_item(ann_item.get_annotation_data())

    @pyqtSlot(int, object)
    def handle_on_screen_added_annotations(self, index: int, annotation_data):
        if not isinstance(annotation_data, FAnnotationData):
            return
        if index == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.add_item(
                annotation_data
            )
        self.list_total_annotations.increase_class(
            annotation_data.get_class_id(),
            annotation_data.get_class_name(),
            annotation_data.get_color()
        )

    @pyqtSlot(int, list)
    def handle_get_results_from_model_thread(self, index: int, result_annotations: list):
        current_annotations = self.thumbnail_carousel.get_annotation_data_by_index(index) or []
        for annotation in current_annotations:
            self.list_total_annotations.decrease_class(annotation.get_class_id())

        self.thumbnail_carousel.handle_on_getting_result_from_model(index, result_annotations)

        if index == self.annotation_scene.get_current_thumb_index():
            self.list_current_annotations.clear_annotations()
            self.annotation_scene.handle_get_result_from_model(result_annotations)

        for annotation in result_annotations:
            if not isinstance(annotation, FAnnotationData):
                continue

            self.list_total_annotations.increase_class(
                annotation.get_class_id(),
                annotation.get_class_name(),
                annotation.get_color()
            )
            if index == self.annotation_scene.get_current_thumb_index():
                self.list_current_annotations.add_item(annotation)

    @pyqtSlot(int, int, object)
    def handle_on_screen_deleted_annotations(self, index_thumb: int, annotation_id: int, deleted_data: object):
        try:
            if index_thumb == self.annotation_scene.get_current_thumb_index():
                self.list_current_annotations.remove_item(annotation_id)
            if isinstance(deleted_data, FAnnotationData):
                self.list_total_annotations.decrease_class(deleted_data.get_class_id())
        except Exception as Error:
            UMessageBox.show_error(str(Error))

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
                updated_annotation
            )
        if not isinstance(prev_annotation,
                          FAnnotationData) or prev_annotation.get_class_id() == updated_annotation.get_class_id():
            return
        else:
            self.list_total_annotations.decrease_class(prev_annotation.get_class_id())
            self.list_total_annotations.increase_class(
                updated_annotation.get_class_id(),
                updated_annotation.get_class_name(),
                updated_annotation.get_color()
            )

    @pyqtSlot(int)
    def handle_on_key_pressed(self, key_number: int):
        if key_number in [int(Qt.Key_V), int(Qt.Key_1)]:
            self.annotate_commander.change_work_mode.emit(EWorkMode.Viewer.value)
        elif key_number in [int(Qt.Key_B), int(Qt.Key_2)]:
            self.annotate_commander.change_work_mode.emit(EWorkMode.BoxAnnotationMode.value)
        elif key_number in [int(Qt.Key_C), int(Qt.Key_3)]:
            self.annotate_commander.change_work_mode.emit(EWorkMode.MaskAnnotationMode.value)
        elif key_number in [int(Qt.Key_S), int(Qt.Key_4)]:
            self.annotate_commander.change_work_mode.emit(EWorkMode.SAM2.value)
        elif key_number == int(Qt.LeftArrow) or key_number == int(Qt.Key_A):
            self.thumbnail_carousel.select_thumbnail_by_direction("left")
        elif key_number == int(Qt.RightArrow) or key_number == int(Qt.Key_D):
            self.thumbnail_carousel.select_thumbnail_by_direction("right")
        elif key_number == int(Qt.Key_N):
            self._drop_current_thumbnail()
        elif key_number == int(Qt.Key_Shift):
            self.annotation_scene.set_work_mode(EWorkMode.ForceDragMode.value)

    @pyqtSlot(int)
    def handle_on_key_released(self, key_number: int):
        if key_number == int(Qt.Key_Shift):
            self.annotation_scene.set_work_mode(self.annotation_scene.get_current_mode().get_previous_mode())

    @pyqtSlot(int)
    def handle_on_key_hold(self, key_number: int):
        if key_number == int(Qt.LeftArrow) or key_number == int(Qt.Key_A):
            self.thumbnail_carousel.select_thumbnail_by_direction("left")
        elif key_number == int(Qt.RightArrow) or key_number == int(Qt.Key_D):
            self.thumbnail_carousel.select_thumbnail_by_direction("right")

    @pyqtSlot(int)
    def handle_on_select_annotation_from_list(self, annotation_id: int):
        self.annotation_scene.select_annotation_by_annotation_id(annotation_id)

    @pyqtSlot(int, bool)
    def handle_on_select_annotation(self, selected_index: int, to_select: bool):
        self.list_current_annotations.select_item(selected_index, to_select)

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
                meta = iio.immeta(file)
                source_width, source_height = meta["shape"]
                thumb = UAnnotationThumbnail(
                    200,
                    175,
                    source_width,
                    source_height,
                    files[index],
                    None,
                    [],
                    index + 1
                )
            elif isinstance(file, FAnnotationItem):
                ann_data = file.get_annotation_data()
                thumb = UAnnotationThumbnail(
                    200,
                    175,
                    file.get_width(),
                    file.get_height(),
                    file.get_image_path(),
                    file.get_dataset_name(),
                    [annotation.copy() for annotation in ann_data],
                    file.get_image_id()
                )
                thumb_status = file.get_annotation_status()
                if thumb_status is not EAnnotationStatus.NO_STATUS:
                    thumb.annotation_status = file.get_annotation_status()
                for annotation in ann_data:
                    self.list_total_annotations.increase_class(
                        annotation.get_class_id(),
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
        self.thumbnail_carousel.update()
        self.thumbnail_carousel.select_last_annotated()

        UMessageBox.show_ok("Изображения загружены!")
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.annotation_scene.center_on_selected()

        self.autosave_timer.start()

    def set_label_work_mode(self, mode: int):
        if mode == EWorkMode.Viewer.value:
            self.selected_label.setText("Просмотр")
        elif mode == EWorkMode.ForceDragMode.value:
            self.selected_label.setText("Перетаскивание")
        elif mode == EWorkMode.MaskAnnotationMode.value:
            self.selected_label.setText("Сегментация")
        elif mode == EWorkMode.BoxAnnotationMode.value:
            self.selected_label.setText("Детекция")
        elif mode == EWorkMode.SAM2.value:
            self.selected_label.setText("SAM2")

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

    def update_labels_by_status(self, status: EAnnotationStatus, to_increase: bool):
        value = 1 if to_increase is True else -1
        if status.value == EAnnotationStatus.ANNOTATED.value:
            self.current_annotated_count += value
            self.label_count_annotated.setText(str(self.current_annotated_count))
        elif status.value == EAnnotationStatus.NO_ANNOTATION.value:
            self.current_not_annotated_count += value
            self.label_count_not_annotated.setText(str(self.current_not_annotated_count))
        elif status.value == EAnnotationStatus.MARKED_DROP.value:
            self.current_dropped_count += value
            self.label_count_dropped.setText(str(self.current_dropped_count))

    def _annotate_image(self):
        thumb_id, matrix = self.annotation_scene.get_selectable_matrix()
        if thumb_id is None or matrix is None:
            return
        if self.thumbnail_carousel.get_current_thumbnail_status() == EAnnotationStatus.PERFORMING_ANNOTATION:
            return
        if self.project.model_worker and self.project.model_worker.is_running():
            self.project.model_worker.add_to_queue(
                thumb_id,
                matrix
            )

    def _load_classes(self):
        self.list_class_selector.clear()
        annotation_classes = self.project.get_classes()
        for class_id in annotation_classes.keys():
            self.list_class_selector.add_class(
                class_id,
                annotation_classes[class_id].name if class_id in annotation_classes else "Unresolved",
                QColor(annotation_classes[class_id].color) if class_id in annotation_classes else QColor(Qt.lightGray)
            )

    def _drop_current_thumbnail(self):
        self.annotation_scene.clean_all_annotations(to_emit=True)
        self.thumbnail_carousel.set_thumbnail_dropped()
        self.thumbnail_carousel.select_thumbnail_by_direction("right")
