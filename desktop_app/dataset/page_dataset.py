import os.path
from typing import Optional

from PyQt5.QtCore import pyqtSlot, QThread
from PyQt5.QtWidgets import QWidget, QStackedWidget, QFileDialog, QMessageBox

from coco.coco_json import cfg_convert_to_coco, build_coco_json, save_coco_json
from coco.coco_project import UCocoProject
from commander import UGlobalSignalHolder
from design.dataset_page import Ui_page_dataset
from dataset.list_datasets import UItemDataset, UListDataset
from dataset.loader import UThreadDatasetLoadAnnotations, UThreadDatasetCopy
from load.export import UDialogExport
from supporting.overlay_widget import UOverlayLoader
from project import RESERVED, DATASETS
from supporting.custom_threads import UProgressThread
from supporting.task_runner import UTaskRunner
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

        #self.button_export.clicked.connect(self.handle_on_button_export_clicked)

        self.button_to_coco.clicked.connect(self.handle_on_click_to_coco)

        self.list_datasets.signal_on_item_clicked.connect(self.move_annotations_to_gallery)

        """self.button_move_dataset_to_reserved.clicked.connect(
            lambda: self.move_selected_dataset(self.list_datasets, self.project.get_datasets(), DATASETS, RESERVED)
        )"""

        #Настройка выбора отображений аннотаций
        self.combo_annotation_type.currentIndexChanged.connect(self.handle_on_type_changed)
        self.combo_annotation_type.set_members({
            "Все аннотации": [EAnnotationType.BoundingBox, EAnnotationType.Segmentation, EAnnotationType.Mask],
            "Ограничительные рамки" : [EAnnotationType.BoundingBox],
            "Полигоны" : [EAnnotationType.Segmentation],
            "Макси": [EAnnotationType.Mask]
        })
        self.combo_annotation_type.setCurrentIndex(0)

        # Привязка ко списку классов
        self.scroll_classes.signal_on_item_clicked.connect(self.on_changed_filter)

        # Привязка к событиям
        if self.commander:
            self.commander.project_load_complete.connect(self.update_dataset_page)
            self.commander.project_updated_datasets.connect(self.update_dataset_page)

        # Объект выполнителя
        self.task_runner: Optional[UTaskRunner] = None
        self.task_tread: Optional[QThread] = None

    def start_task_thread(self, tasks: list[tuple[callable, tuple, dict]]):
        self.task_runner = UTaskRunner(tasks)

        self.task_tread = QThread()
        self.task_runner.moveToThread(self.task_tread)

        self.task_tread.started.connect(self.task_runner.run)
        #self.task_tread.finished.connect(self.task_tread.deleteLater)

        self.task_runner.finished.connect(self.task_tread.quit)
        self.task_runner.finished.connect(self.on_task_runner_finished)

        self.task_tread.start()

    @pyqtSlot()
    def on_task_runner_finished(self):
        self.update_dataset_page()
        self.task_runner = None
        self.commander.project_updated_datasets.emit()

    @pyqtSlot()
    def update_dataset_page(self):
        self.create_list_dataset()
        self.fill_filter_list()
        self.view_gallery.clear_scene()
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    def on_changed_filter(self, class_id: int, selected: bool):
        if class_id in self.filter_dict:
            self.filter_dict[class_id] = selected
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    def go_to_another_page(self, page_index: int):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(page_index)

    def move_annotations_to_gallery(self, dataset: str, annotations: dict[str, list[FAnnotationItem]]):
        list_annotations: list[FAnnotationItem] = list()
        for key, list_a in annotations.items():
            list_annotations += list_a
        self.view_gallery.clear_scene()
        self.view_gallery.set_dataset_annotations(list_annotations)
        self.view_gallery.filter_images(self.filter_dict, self.type_list)

    @pyqtSlot()
    def handle_on_button_export_clicked(self):
        dialog = UDialogExport(self.project.get_annotations(), self.project.get_classes())
        dialog.signal_done.connect(self.handle_on_export_window_done)
        self.commander.set_block(True)
        if dialog.exec_():
            self.commander.set_block(False)

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
    def handle_on_click_to_coco(self):
        images, annotations, categories = cfg_convert_to_coco(self.project.get_annotations(), self.project.get_classes())

        info = {
            "name": "Varan-Master",
            "description": "Varan",
            "version": "0.1",
            "author": "Ivan",
            "year": 2025
        }

        coco_json = build_coco_json(images, annotations, categories, info, [])

    @pyqtSlot()
    def handle_on_click_button_clear_all_selections(self):
        self.view_gallery.clear_all_selections()

    @pyqtSlot()
    def handle_on_click_button_delete_annotations(self):
        if self.task_runner:
            return

        selected_annotations = self.view_gallery.get_selected_annotation()
        if len(selected_annotations) > 0 and UMessageBox.ask_confirmation("Удалить аннотации из проекта?"):
            task = [
                (self.project.remove_list_of_annotations, (selected_annotations,), {}),
                (self.project.save, (), {})
            ]
            self.start_task_thread(task)

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

            self.start_task_thread(tasks)
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
            widget = self.list_datasets.item(selected_index).listWidget()
            if isinstance(widget, UItemDataset) and widget.get_dataset_name() == selected_name:
                self.list_datasets.setCurrentIndex(selected_index)

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