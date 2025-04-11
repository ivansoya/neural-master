import os.path
import shutil
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QCoreApplication, pyqtSlot
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QWidget, QStackedWidget, QListWidget, QFileDialog, QMessageBox, QListWidgetItem, \
    QApplication
from networkx.algorithms.traversal.edgebfs import REVERSE

from commander import UGlobalSignalHolder, ECommanderStatus
from design.dataset_page import Ui_page_dataset
from dataset.list_datasets import UItemDataset, UListDataset
from dataset.loader import UOverlayLoader, UThreadDatasetLoadAnnotations, UThreadDatasetCopy
from project import UTrainProject, RESERVED, DATASETS
from supporting.custom_threads import UProgressThread
from utility import UMessageBox, FAnnotationItem, FAnnotationClasses

DATASET_ALL = "All Annotations"

class UThreadDisplayDataset(QThread):
    signal_on_image_loaded = pyqtSignal(str, str, list)
    signal_on_progress_changed = pyqtSignal(str, int, int)
    signal_on_ended = pyqtSignal()
    signal_on_error = pyqtSignal(str)

    def __init__(self,
                 classes: FAnnotationClasses,
                 annotations: dict[str, list[FAnnotationItem]],
                 show_dict: dict[int, bool],
                 image_size: int = 200
    ):
        super().__init__()

        self.annotations = annotations
        self.size = image_size
        self.ann_len = sum(len(ann) for ann in self.annotations.values())
        self.classes = classes
        self.show_dict = show_dict

    def run(self):
        indicator = 1
        for dataset, annotation_data in self.annotations.items():
            for index in range(len(annotation_data)):
                data = self.annotations[dataset][index].get_annotation_data()
                image_path = self.annotations[dataset][index].get_image_path()
                annotation_list: list[tuple[int, int, int, int, int, QColor]] = list()
                for annotation in data:
                    color = self.classes.get_color(annotation.ClassID) or QColor(Qt.gray)
                    annotation_list.append(
                        (annotation.ClassID, annotation.X, annotation.Y, annotation.Width, annotation.Height, color)
                    )
                self.signal_on_image_loaded.emit(image_path, dataset, annotation_list)
                indicator += 1
                self.signal_on_progress_changed.emit(image_path, indicator, self.ann_len)
        self.signal_on_ended.emit()

class UPageDataset(QWidget, Ui_page_dataset):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.commander = commander
        self.project = project

        # Дополнительные параметры
        self.filter_dict: dict[int, bool] = dict()

        # Дополнительные виджеты
        self.overlay: Optional[UOverlayLoader] = None
        self.thread_load_annotations: Optional[UThreadDatasetLoadAnnotations] = None
        self.thread_copy: Optional[UThreadDatasetCopy] = None
        self.thread_display: Optional[UThreadDisplayDataset] = None

        self.thread_custom: Optional[UProgressThread] = None

        # Привязка к кнопкам
        self.button_add_dataset.clicked.connect(self.add_dataset)
        self.button_refresh.clicked.connect(self.update_dataset_page)
        self.button_selected_to_annotate.clicked.connect(self.load_selected_to_annotate_page)
        self.button_choose_all.clicked.connect(self.handle_on_click_button_choose_all)
        self.button_reset_selected.clicked.connect(self.handle_on_click_button_clear_all_selections)
        self.button_delete_selected.clicked.connect(self.handle_on_click_button_delete_annotations)

        self.list_datasets.signal_on_item_clicked.connect(self.move_annotations_to_gallery)
        self.list_reserved.signal_on_item_clicked.connect(self.move_annotations_to_gallery)

        self.button_move_dataset_to_reserved.clicked.connect(
            lambda: self.move_selected_dataset(self.list_datasets, self.project.get_datasets(), DATASETS, RESERVED)
        )

        # Привязка к спискам
        self.list_datasets.itemClicked.connect(self.on_item_current_dataset_selected)
        self.list_reserved.itemClicked.connect(self.on_item_reserved_selected)

        # Привязка ко списку классов
        self.scroll_classes.signal_on_item_clicked.connect(self.on_changed_filter)

        # Привязка к событиям
        if self.commander:
            self.commander.project_load_complete.connect(self.update_dataset_page)
            self.commander.project_updated_datasets.connect(self.update_dataset_page)

    def update_dataset_page(self):
        self.create_list_dataset()
        self.create_list_reserved()
        self.fill_filter_list()
        self.view_gallery.clear_scene()
        self.view_gallery.filter_images(self.filter_dict)

    def on_changed_filter(self, class_id: int, selected: bool):
        if class_id in self.filter_dict:
            self.filter_dict[class_id] = selected
        self.view_gallery.filter_images(self.filter_dict)

    def go_to_another_page(self, page_index: int):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(page_index)

    def move_annotations_to_gallery(self, dataset: str, annotations: dict[str, list[FAnnotationItem]]):
        list_annotations: list[FAnnotationItem] = list()
        for key, list_a in annotations.items():
            list_annotations += list_a
        self.view_gallery.clear_scene()
        self.view_gallery.set_dataset_annotations(list_annotations)
        self.view_gallery.filter_images(self.filter_dict)

    def add_dataset(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с датасетом", "")
        if not path:
            return
        dataset_name = os.path.basename(path)
        if dataset_name in self.project.datasets:
            UMessageBox.show_error(f"Данный датасет {dataset_name} уже есть в проекте!")
            return
        classes_path = os.path.join(path, "classes.txt").replace('\\', '/')
        if any(
            not os.path.exists(os.path.join(path, folder).replace('\\', '/'))
            for folder in ["images", "labels"]
        ) or not os.path.exists(classes_path) or not os.path.isfile(classes_path):
            UMessageBox.show_error(f"Выбранный датасет {dataset_name} не валидный!")
            return

        with open(classes_path, "r") as file:
            classes_list = [line.strip() for line in file]

        if classes_list != [cls.Name for cls in self.project.classes.get_all_classes()]:
            UMessageBox.show_error(f"Классы выбранного датасета не совпадают с классами проекта!")
            return

        if (self.overlay or
            (self.thread_copy and self.thread_copy.isRunning()) or
            (self.thread_load_annotations and self.thread_load_annotations.isRunning())
        ):
            return

        self.overlay = UOverlayLoader(self.dataset_display)

        self.thread_copy = UThreadDatasetCopy(self.project, path)

        self.thread_copy.signal_on_copy.connect(self.overlay.update_progress)
        self.thread_copy.signal_on_error.connect(self.make_error_with_copy)
        self.thread_copy.signal_on_ended.connect(self.load_annotations)

        self.thread_copy.start()

    @pyqtSlot()
    def load_selected_to_annotate_page(self):
        if self.parent() and isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(2)
            self.commander.set_status(ECommanderStatus.Annotation)
        self.commander.loaded_images_to_annotate.emit(self.view_gallery.get_selected_annotation())

    @pyqtSlot()
    def handle_on_click_button_choose_all(self):
        self.view_gallery.set_all_selected()

    @pyqtSlot()
    def handle_on_click_button_clear_all_selections(self):
        self.view_gallery.clear_all_selections()

    @pyqtSlot()
    def handle_on_click_button_delete_annotations(self):
        list_images = self.view_gallery.get_selected_annotation()
        if self.thread_custom and self.thread_custom.isRunning():
            UMessageBox.show_error("Уже работает поток, выполняя другое действие!")
            return
        dataset_type, list_widget, selected_item = (
            (DATASETS, self.list_datasets, self.list_datasets.selectedItems()[0]) if self.list_datasets.selectedItems()
            else (REVERSE, self.list_reserved, self.list_reserved.selectedItems()[0]) if self.list_reserved.selectedItems()
            else (None, None, None)
        )
        if dataset_type and selected_item:
            self.thread_custom = UProgressThread(list_images, self.project.remove_annotation, dataset_type)
            self.thread_custom.signal_on_finish.connect(self.handle_on_finish_delete_annotations)
            self.thread_custom.set_finish_params((list_widget, selected_item))
            self.thread_custom.start()
        else:
            UMessageBox.show_error("Не был выбран датасет, из которого нужно удалить аннотации")

    @pyqtSlot(tuple)
    def handle_on_finish_delete_annotations(self, params: tuple):
        list_widget, selected_item = params
        if isinstance(list_widget, UListDataset) and isinstance(selected_item, QListWidgetItem):
            self.view_gallery.clear_all_selections()
            list_widget.itemClicked.emit(selected_item)
            list_widget.update_all_items()
        else:
            UMessageBox.show_error("Ошибка во время завершения потока удаления аннотаций!")
            return

    def load_annotations(self, dataset_name: str):
        if self.thread_copy:
            self.thread_copy.deleteLater()
            self.thread_copy = None

        if self.overlay is None:
            UMessageBox.show_error("Не удается найти объект UOverlayLoader! Невозможно загрузить аннотации!")
            return

        self.project.add_dataset(dataset_name)

        self.thread_load_annotations = UThreadDatasetLoadAnnotations(self.project, [dataset_name])
        self.thread_load_annotations.signal_start_dataset.connect(self.overlay.update_label_dataset)
        self.thread_load_annotations.signal_loaded_label.connect(self.overlay.update_progress)
        self.thread_load_annotations.signal_end_load.connect(self.end_add_dataset)

        self.thread_load_annotations.signal_error.connect(self.make_error_with_load_annotations)
        self.thread_load_annotations.signal_warning.connect(UPageDataset.print_warning)

        self.thread_load_annotations.start()


    def end_add_dataset(self, datasets: list[str]):
        error = self.project.save()
        if error:
            UMessageBox.show_error(error)
        else:
            UMessageBox.show_error("Датасет был успешно добавлен в проект и загружен!", "Успех!", int(QMessageBox.Ok))
        # Обновление списка датасетов
        self.list_datasets.clear()
        self.create_list_dataset()
        self.close_overlay()

    def make_error_with_load_annotations(self, dataset: str, error_str: str):
        UMessageBox.show_error(error_str)

        self.project.remove_dataset(dataset)
        self.project.remove_all_annotations_from_dataset(dataset)
        self.project.remove_project_folder(dataset)

        self.close_overlay()

    def remove_dataset(self, widget_list: UListDataset, dataset_list: list[str], dataset_type: str):
        widget = UListDataset.get_item_widget(widget_list)
        if not widget or (widget.name not in dataset_list):
            UMessageBox.show_error("Датасет не выбран!")
            return

        message_confirm = QMessageBox()
        message_confirm.setIcon(QMessageBox.Warning)
        message_confirm.setWindowTitle("Подтвердите безвозвратное удаление!")
        message_confirm.setText(f"Вы действительно хотите удалить {widget.name}?")
        message_confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message_confirm.button(QMessageBox.Yes).setText("Подтвердить")
        message_confirm.button(QMessageBox.No).setText("Отменить")

        result = message_confirm.exec_()
        if result == QMessageBox.Yes:
            self.project.remove_dataset_from_project(widget.name, dataset_type)
            self.view_gallery.clear_scene()
            self.project.save()
            UMessageBox.show_error(f"Датасет {widget.name} удален из проекта!", "Успех", int(QMessageBox.Ok))
            self.commander.project_updated_datasets.emit()
        else:
            return

    def move_selected_dataset(
            self,
            widget_list: UListDataset,
            dataset_list: list[str],
            source_type: str,
            target_type: str
        ):
        if self.overlay or (self.thread_copy and self.thread_copy.isRunning()):
            return

        dataset_item = UListDataset.get_item_widget(widget_list)
        if not dataset_item or (dataset_item.name not in dataset_list):
            return
        path_to_dataset_source = os.path.join(self.project.path, source_type, dataset_item.name).replace('\\', '/')

        self.overlay = UOverlayLoader(self.dataset_display)

        self.thread_copy = UThreadDatasetCopy(self.project, path_to_dataset_source, target_type)

        self.thread_copy.signal_on_copy.connect(self.overlay.update_progress)
        self.thread_copy.signal_on_error.connect(self.make_error_with_copy)
        self.thread_copy.signal_on_ended.connect(
            lambda dataset_name: self.end_swap_dataset(dataset_name, source_type, target_type)
        )

        self.thread_copy.start()

    def end_swap_dataset(self, dataset_name: str, source_type: str, target_type: str):
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)

        self.project.swap_annotations(dataset_name, source_type, target_type)
        self.project.remove_all_annotations_from_dataset(dataset_name, source_type)
        self.project.remove_dataset(dataset_name, source_type)

        self.project.add_dataset(dataset_name, target_type)
        self.project.save()

        self.project.remove_project_folder(dataset_name, source_type)

        self.commander.project_updated_datasets.emit()


    def on_item_current_dataset_selected(self):
        self.button_move_dataset_to_reserved.setText("Резервировать датасет")
        self.button_move_selected_to_reserved.setText("Резервировать выбранное")

        self.button_move_dataset_to_reserved.clicked.connect(
            lambda : self.move_selected_dataset(self.list_datasets, self.project.get_datasets(), DATASETS, RESERVED)
        )
        self.button_delete_dataset.clicked.connect(
            lambda: self.remove_dataset(self.list_datasets, self.project.get_datasets(), DATASETS)
        )

        self.list_reserved.clearSelection()

    def on_item_reserved_selected(self):
        self.button_move_dataset_to_reserved.setText("Восстановить датасет")
        self.button_move_selected_to_reserved.setText("Восстановить выбранное")

        self.button_move_dataset_to_reserved.clicked.connect(
            lambda: self.move_selected_dataset(self.list_reserved, self.project.get_reserved(), RESERVED, DATASETS)
        )
        self.button_delete_dataset.clicked.connect(
            lambda: self.remove_dataset(self.list_reserved, self.project.get_reserved(), RESERVED)
        )

        self.list_datasets.clearSelection()

    def create_list_reserved(self):
        selected_index, selected_name = self.list_reserved.get_selected_item()
        self.list_reserved.clear()
        for dataset in self.project.reserved:
            try:
                reserved_temp = {dataset: self.project.get_reserved_annotations()[dataset]}
                self.list_reserved.add_dataset_item(
                    UItemDataset(
                        dataset,
                        reserved_temp
                    )
                )
            except Exception as error:
                return str(error)

        if 0 <= selected_index < self.list_reserved.count():
            widget = self.list_reserved.item(selected_index).listWidget()
            if isinstance(widget, UItemDataset) and widget.get_dataset_name() == selected_name:
                self.list_reserved.setCurrentIndex(selected_index)

    def create_list_dataset(self):
        selected_index, selected_name = self.list_datasets.get_selected_item()
        self.list_datasets.clear()
        # Создание общего предмета
        sum_len = sum(len(ann_list) for ann_list in self.project.current_annotations.values())
        if sum_len == 0:
            return
        all_item = UItemDataset(
            DATASET_ALL,
            self.project.current_annotations
        )
        self.list_datasets.add_dataset_item(all_item)

        # Создание отдельных датасетов
        for dataset in self.project.datasets:
            try:
                annotation_temp = {dataset: self.project.get_current_annotations()[dataset]}
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

        for class_id, class_t in self.project.classes.get_items():
            self.scroll_classes.add_filter(class_t.Color, class_id, class_t.Name)
            self.filter_dict[class_id] = True


    def make_error_with_copy(self, error_str: str):
        UMessageBox.show_error(error_str)
        self.close_overlay()

    @staticmethod
    def print_warning(error_str: str):
        UMessageBox.show_error(error_str, "Предупреждение!", QMessageBox.Warning)

    def close_overlay(self):
        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None