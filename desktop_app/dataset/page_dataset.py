import os
from typing import Optional

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QWidget, QStackedWidget, QDialog, QFileDialog

from coco.coco_json import cfg_convert_to_coco, build_coco_json, make_coco_json, load_coco_json, \
    make_annotation_dict_from_coco
from coco.coco_project import UCocoProject
from commander import UGlobalSignalHolder
from design.dataset_page import Ui_page_dataset
from dataset.list_datasets import UItemDataset
from dataset.loader import UThreadDatasetLoadAnnotations, UThreadDatasetCopy
from export.export import UDialogExport
from supporting.overlay_widget import UOverlayLoader
from supporting.custom_threads import UProgressThread
from supporting.qt_general import terminate_closable_dialog
from utility import UMessageBox, FAnnotationItem, EAnnotationType

DATASET_ALL = "All Annotations"

class UPageDataset(QWidget, Ui_page_dataset):
    def __init__(self, commander: UGlobalSignalHolder, project: UCocoProject):
        super().__init__()
        self.setupUi(self)

        self.commander = commander
        self.project = project

        # Дополнительные параметры
        self.filter_dict: dict[int, bool] = dict()
        self.type_list: list[EAnnotationType] = list()

        self.last_selected: int = -1

        # Дополнительные виджеты
        self.overlay: Optional[UOverlayLoader] = None
        self.thread_load_annotations: Optional[UThreadDatasetLoadAnnotations] = None
        self.thread_copy: Optional[UThreadDatasetCopy] = None

        self.thread_custom: Optional[UProgressThread] = None

        # Привязка к кнопкам
        #self.button_add_dataset.clicked.connect(self.add_dataset)
        self.button_refresh.clicked.connect(self.update_dataset_page)
        self.button_selected_to_annotate.clicked.connect(self.load_selected_to_annotate_page)
        self.button_choose_all.clicked.connect(self.handle_on_click_button_choose_all)
        self.button_reset_selected.clicked.connect(self.handle_on_click_button_clear_all_selections)
        self.button_delete_selected.clicked.connect(self.handle_on_click_button_delete_annotations)

        self.button_change_dataset.clicked.connect(self.handle_on_button_rename_dataset_annotations_clicked)
        self.button_rename_dataset.clicked.connect(self.handle_on_button_rename_dataset_clicked)

        self.button_export.clicked.connect(self.handle_on_button_export_clicked)

        self.button_import.clicked.connect(self.handle_on_button_import_clicked)

        self.list_datasets.signal_on_item_clicked.connect(self.move_annotations_to_gallery)

        #Настройка выбора отображений аннотаций
        self.combo_annotation_type.currentIndexChanged.connect(self.handle_on_type_changed)
        self.combo_annotation_type.set_members({
            "Все аннотации": [EAnnotationType.BoundingBox, EAnnotationType.Segmentation, EAnnotationType.Mask],
            "Ограничительные рамки" : [EAnnotationType.BoundingBox],
            "Полигоны" : [EAnnotationType.Segmentation],
            "Маски": [EAnnotationType.Mask]
        })
        self.combo_annotation_type.setCurrentIndex(0)

        # Привязка ко списку классов
        self.scroll_classes.signal_on_item_clicked.connect(self.on_changed_filter)

        # Привязка к событиям
        if self.commander:
            self.commander.project_load_complete.connect(self.update_dataset_page)
            self.commander.project_updated.connect(self.update_dataset_page)

    @pyqtSlot()
    def on_task_runner_finished(self):
        self.commander.project_updated.emit()

    @pyqtSlot()
    def update_dataset_page(self):
        self.create_list_dataset()
        self.fill_filter_list()
        self.set_selected_dataset_to_gallery()

    def on_changed_filter(self, class_id: int, selected: bool):
        if class_id in self.filter_dict:
            self.filter_dict[class_id] = selected
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    def go_to_another_page(self, page_index: int):
        stack = self.parent()
        if isinstance(stack, QStackedWidget):
            stack.setCurrentIndex(page_index)

    @pyqtSlot(str, object)
    def move_annotations_to_gallery(self, dataset: str, annotations: dict[str, list[FAnnotationItem]]):
        list_annotations: list[FAnnotationItem] = list()
        for key, list_a in annotations.items():
            list_annotations += list_a
        self.view_gallery.clear_scene()
        self.view_gallery.set_dataset_annotations(list_annotations)
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    def set_selected_dataset_to_gallery(self):
        selected_items = self.list_datasets.selectedItems()

        if not selected_items or len(selected_items) == 0:
            self.move_annotations_to_gallery("", {})
        else:
            selected_item = self.list_datasets.itemWidget(selected_items[0])
            if isinstance(selected_item, UItemDataset):
                self.move_annotations_to_gallery(selected_item.get_dataset_name(), selected_item.get_annotations())
            else:
                self.move_annotations_to_gallery("", {})

    @pyqtSlot()
    def handle_on_button_export_clicked(self):
        dialog = UDialogExport(self.project)
        self.commander.set_block(True)
        if dialog.exec_() == QDialog.Accepted:
            export_path, chosen_class_ids, chosen_datasets, train_percentage = dialog.get_result()

            if train_percentage is None:
                task = [
                    (self.project.simple_export_with_refactor, (export_path, chosen_datasets, chosen_class_ids,), {})
                ]
            else:
                task = [
                    (self.project.simple_txt_export_with_refactor, (export_path, chosen_datasets, chosen_class_ids,), {})
                ]

            if self.project.start_task_thread(task, [self.handle_on_ended_export], []) is False:
                UMessageBox.show_error("Невозможно запустить экспорт, поток занят!")

            self.commander.task_start.emit(f"Идет экспорт датасета!")

        self.commander.set_block(False)

    @pyqtSlot()
    def handle_on_ended_export(self):
        if self.commander:
            self.commander.task_finished.emit("Экспорт завершен!")

    @pyqtSlot(str, list, object)
    def handle_on_export_window_done(self, path: str, dataset_list: list[str], refactor_class_dict: object):
        self.commander.start_export.emit(path, dataset_list, refactor_class_dict)

    @pyqtSlot()
    def load_selected_to_annotate_page(self):
        if self.commander:
            self.commander.go_to_page_annotation.emit()
            self.commander.loaded_images_to_annotate.emit(self.view_gallery.get_selected_annotation())

    @pyqtSlot()
    def handle_on_click_button_choose_all(self):
        self.view_gallery.set_all_selected()

    @pyqtSlot()
    def handle_on_button_import_clicked(self):
        confirm_window = UMessageBox.ask_confirmation(
            "Выберите режим импорта",
            "Внимание",
            "Слияние",
            "Добавление"
        )
        if confirm_window is None:
            return

        json_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите json импортируемых данных",
            os.getcwd(),
            "Json проекты (*.json);;Все файлы (*)"
        )

        if not os.path.isfile(json_path):
            return

        # Обработка слияния
        if confirm_window is True:
            task = [
                (self.run_import, (json_path, True, ), {}),
                (self.project.save, (), {})
            ]
        else:
            task = [
                (self.run_import, (json_path, False, ), {}),
                (self.project.save, (), {})
            ]

        if self.project.start_task_thread(task, [self.handle_on_ended_import], [self.handle_on_error_import]):
            if self.commander: self.commander.task_start.emit("Начат импорт!")

    def run_import(self, path_import: str, is_merge: bool):
        _, _, annotations, images, classes = load_coco_json(path_import)

        loaded_annotations, classes = make_annotation_dict_from_coco(images, annotations, classes, os.path.dirname(path_import))

        if not self.project.is_classes_equal(classes):
            raise Exception("Набор классов импортируемого датасета не совпадает с текущим!")

        if is_merge:
            for dataset, ann_items in loaded_annotations.items():
                self.project.update_annotations(ann_items, dataset)
        else:
            for dataset, ann_items in loaded_annotations.items():
                self.project.import_annotated_images(ann_items, dataset)

    @pyqtSlot(str)
    def handle_on_error_import(self, error_text: str):
        if self.commander:
            self.commander.task_error.emit("Импорт не выполнен!")
            self.commander.project_updated.emit()
        UMessageBox.show_error(f"Произошла ошибка во время импорта: {error_text}")

    @pyqtSlot()
    def handle_on_ended_import(self):
        if self.commander:
            self.commander.task_finished.emit("Импорт завершен!")
            self.commander.project_updated.emit()

    @pyqtSlot()
    def handle_on_click_button_clear_all_selections(self):
        self.view_gallery.clear_all_selections()

    @pyqtSlot()
    def handle_on_button_rename_dataset_clicked(self):
        self._rename_dataset_common(
            get_source_data_func=lambda: self._get_selected_dataset(),
            rename_func=self.project.rename_dataset,
            error_no_selection_msg="Датасет не выбран!",
            error_no_name_msg="Введите или выберите название датасета!"
        )

    @pyqtSlot()
    def handle_on_button_rename_dataset_annotations_clicked(self):
        self._rename_dataset_common(
            get_source_data_func=self.view_gallery.get_selected_annotation,
            rename_func=self.project.rename_dataset_annotations,
            error_no_selection_msg="Выберите изображенияЙ",
            error_no_name_msg="Введите или выберите название датасета!"
        )

    def _get_selected_dataset(self):
        ret, selected_dataset = self.list_datasets.get_selected_item()
        return selected_dataset if ret != -1 else None

    def _rename_dataset_common(
            self,
            get_source_data_func,
            rename_func,
            error_no_selection_msg: str,
            error_no_name_msg: str
    ):
        source_data = get_source_data_func()
        if not source_data:
            UMessageBox.show_error(error_no_selection_msg)
            return

        self.commander.set_block(True)
        new_dataset_name = terminate_closable_dialog(self.project.get_annotations().keys())
        self.commander.set_block(False)

        if new_dataset_name is None:
            return

        if len(new_dataset_name) == 0:
            UMessageBox.show_error(error_no_name_msg)
            return

        task = [
            (rename_func, (source_data, new_dataset_name), {}),
            (self.project.save, (), {})
        ]

        self.project.start_task_thread(task, [self.create_list_dataset, self.set_selected_dataset_to_gallery], [])

    @pyqtSlot()
    def handle_on_click_button_delete_annotations(self):
        selected_annotations = self.view_gallery.get_selected_annotation()
        if len(selected_annotations) > 0 and UMessageBox.ask_confirmation("Удалить аннотации из проекта?"):
            tasks = [
                (self.project.remove_list_of_annotations, (selected_annotations,), {}),
                (self.project.save, (), {})
            ]
            if self.project.start_task_thread(tasks, [self.on_task_runner_finished], []) is False:
                UMessageBox.show_error("Поток сейчас занят, попробуйте позже!")

    @pyqtSlot()
    def handle_on_type_changed(self):
        self.type_list = self.combo_annotation_type.get_current_enum()
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    @pyqtSlot()
    def handle_on_clicked_button_remove_dataset(self):
        ret, dataset_name = self.list_datasets.get_selected_item()
        if ret == -1:
            return

        if UMessageBox.ask_confirmation(f"Подтвердите удаление всех аннотаций в {dataset_name}"):
            tasks = [
                (self.project.remove_dataset, (dataset_name,), {}),
                (self.project.save, (), {})
            ]

            if self.project.start_task_thread(tasks, [self.on_task_runner_finished], []) is False:
                UMessageBox.show_error("Поток сейчас занят, попробуйте позже!")
        else:
            return

    def create_list_dataset(self):
        selected_index, selected_name = self.list_datasets.get_selected_item()
        dict_annotations = self.project.get_annotations()

        self.list_datasets.clear()
        # Создание общего предмета
        sum_len = sum(len(ann_list) for ann_list in dict_annotations.values())
        if sum_len == 0:
            return
        all_item = UItemDataset(
            "Все аннотации",
            dict_annotations
        )
        self.list_datasets.add_dataset_item(all_item)

        # Создание отдельных датасетов
        for dataset in dict_annotations.keys():
            try:
                annotation_temp = {dataset: dict_annotations[dataset]}
                self.list_datasets.add_dataset_item(
                    UItemDataset(
                        dataset,
                        annotation_temp
                    )
                )
            except Exception as error:
                return str(error)

        if 0 <= selected_index < self.list_datasets.count():
            list_item = self.list_datasets.item(selected_index)
            widget = self.list_datasets.itemWidget(list_item)
            if isinstance(widget, UItemDataset) and widget.get_dataset_name() == selected_name:
                self.list_datasets.setCurrentRow(selected_index)

    def fill_filter_list(self):
        widget = self.scroll_classes.widget()
        if widget is None:
            return
        layout = widget.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for class_id, class_t in self.project.get_classes().items():
            self.scroll_classes.add_filter(class_t.color, class_id, class_t.name)
            self.filter_dict[class_id] = True

    def make_error_with_copy(self, error_str: str):
        UMessageBox.show_error(error_str)
        self.close_overlay()

    @staticmethod
    def print_warning(error_str: str):
        UMessageBox.show_warning(error_str)

    def close_overlay(self):
        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None