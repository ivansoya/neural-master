import sys
from typing import Optional

from PyQt5.QtCore import pyqtSlot, QThread
from PyQt5.QtWidgets import QApplication, QMainWindow

from coco.coco_project import UCocoProject
from dataset.export_thread import UExportWorker
from design.train_app import Ui_TrainApp
from commander import UGlobalSignalHolder, ECommanderStatus
from annotation.page_annotation import UPageAnnotation
from stats.page_classes import UPageClasses
from dataset.page_dataset import UPageDataset
from load.page_load_create import UPageLoader
from page_model import UPageModel
from project import UTrainProject
from utility import UMessageBox


class TrainApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.project = UCocoProject()

        self.global_signal_holder = UGlobalSignalHolder()
        QApplication.instance().installEventFilter(self.global_signal_holder)

        self.export_thread: Optional[QThread] = None
        self.export_worker: Optional[UExportWorker] = None

        self.page_save_load = UPageLoader(self.global_signal_holder, self.project)
        self.page_dataset = UPageDataset(self.global_signal_holder, self.project)
        self.page_annotation = UPageAnnotation(self.global_signal_holder, self.project)
        self.page_classes = UPageClasses(self.global_signal_holder, self.project)
        self.page_model = UPageModel(self.global_signal_holder, self.project)

        self.stacked_page_loader.addWidget(self.page_save_load)
        self.stacked_page_loader.addWidget(self.page_dataset)
        self.stacked_page_loader.addWidget(self.page_annotation)
        self.stacked_page_loader.addWidget(self.page_classes)
        self.stacked_page_loader.addWidget(self.page_model)

        self.stacked_page_loader.setCurrentIndex(0)

        self.button_to_datasets_settings.clicked.connect(lambda: self.change_page(1, ECommanderStatus.DatasetView))
        self.button_to_annotation_scene.clicked.connect(lambda: self.change_page(2, ECommanderStatus.Annotation))
        self.button_to_statistics.clicked.connect(lambda: self.change_page(3, ECommanderStatus.Statistics))
        self.button_to_model.clicked.connect(lambda: self.change_page(4, ECommanderStatus.LoadModel))

        self.nav_bar.setVisible(False)
        self.nav_bar.setEnabled(False)

        self.label_export.setVisible(False)

        self.global_signal_holder.project_load_complete.connect(self.handle_on_load_project)

        self.global_signal_holder.start_export.connect(self.handle_on_start_export)

        self.global_signal_holder.go_to_page_datasets.connect(
            lambda: self.change_page(1, ECommanderStatus.DatasetView)
        )
        self.global_signal_holder.go_to_page_annotation.connect(
            lambda: self.change_page(2, ECommanderStatus.Annotation)
        )

    def change_page(self, page_index: int, status: ECommanderStatus):
        self.stacked_page_loader.setCurrentIndex(page_index)
        self.global_signal_holder.set_status(status)

    @pyqtSlot()
    def handle_on_load_project(self):
        self.nav_bar.setVisible(True)
        self.nav_bar.setEnabled(True)
        self.change_page(1, ECommanderStatus.DatasetView)

    @pyqtSlot(str, list, object)
    def handle_on_start_export(self, path: str, dataset_list: list[str], refactor_dict: dict[str, (int, str)] | None):
        if self.export_thread and self.export_thread.isRunning():
            UMessageBox.show_error("Экспорт уже запущен!")
            return

        self.export_thread = QThread()
        self.export_worker = UExportWorker(
            self.project.get_current_annotations(),
            path,
            dataset_list,
            refactor_dict
        )
        self.export_worker.moveToThread(self.export_thread)

        self.export_thread.started.connect(self.export_worker.run)
        self.export_thread.finished.connect(self._delete_thread)

        self.export_worker.signal_done.connect(self.handle_on_done_export)
        self.export_worker.signal_error.connect(self.handle_on_error_export)
        self.export_worker.signal_process.connect(self.handle_on_process_export)

        self.label_export.setVisible(True)
        self.label_export.setText(f"Старт экспорта!")

        self.export_thread.start()

    @pyqtSlot(float)
    def handle_on_process_export(self, percentage: float):
        self.label_export.setText(f"Идет экспорт: {round(100 * percentage, 2)}%")

    @pyqtSlot(str)
    def handle_on_error_export(self, message: str):
        self.label_export.setText("")
        self.label_export.setVisible(False)
        self._delete_worker()
        self.export_thread.quit()
        UMessageBox.show_error(message)

    @pyqtSlot()
    def handle_on_done_export(self):
        self.label_export.setText("")
        self.label_export.setVisible(False)
        self._delete_worker()
        self.export_thread.quit()
        UMessageBox.show_ok("Экспорт завершен!")

    def _delete_thread(self):
        self.export_thread.deleteLater()
        self.export_thread = None

    def _delete_worker(self):
        self.export_worker.deleteLater()
        self.export_worker = None

def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
