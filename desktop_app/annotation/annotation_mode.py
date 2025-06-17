from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QPointF, QRectF, pyqtSlot, QObject, Qt
from PyQt5.QtGui import QMouseEvent, QKeyEvent
from PyQt5.QtWidgets import QGraphicsView, QGraphicsItem, QWidget, QApplication, QMenu

from annotation.annotation_box import UAnnotationBox
from annotation.annotation_item import UAnnotationItem
from annotation.annotation_mask import UAnnotationMask
from commander import UGlobalSignalHolder, UAnnotationSignalHolder
from supporting.functions import clamp, get_clamped_pos
from utility import FAnnotationData

if TYPE_CHECKING:
    from annotation.annotation_scene import UAnnotationGraphicsView


class EWorkMode(Enum):
    DragMode = 1
    ForceDragMode = 2
    GettingResultsMode = 3
    BoxAnnotationMode = 4
    MaskAnnotationMode = 5

class UBaseAnnotationMode(ABC):
    @abstractmethod
    def start_mode(self, prev_mode: EWorkMode):
        pass

    @abstractmethod
    def end_mode(self, mode: EWorkMode):
        pass

    @abstractmethod
    def get_previous_mode(self) -> EWorkMode | None:
        pass

    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def on_press_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_move_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_release_mouse(self, event: QMouseEvent | None):
        pass

    @abstractmethod
    def on_key_press(self, event: QKeyEvent):
        pass

    @abstractmethod
    def on_key_release(self, event: QKeyEvent):
        pass

    @abstractmethod
    def on_select_item(self, item: UAnnotationItem):
        pass

    @abstractmethod
    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        pass

    @abstractmethod
    def on_delete_item(self, item: UAnnotationItem):
        pass

class UDragAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.DragMode
        self.previous_mode: Optional[EWorkMode] = None

        self.mask_adding_point_mode = False
        self.last_mask: Optional[UAnnotationMask] = None

    def start_mode(self, prev_mode):
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        self.mask_adding_point_mode = False
        self.last_mask = None
        return

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        self.mask_adding_point_mode = False
        self.last_mask = None
        return

    def on_move_mouse(self, event):
        return

    def on_press_mouse(self, event):
        image = self.scene.get_image()
        if not image:
            return

        if event.button() == Qt.LeftButton and self.mask_adding_point_mode:
            if self.last_mask is None:
                return
            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)
            self.last_mask.add_point(cursor_pos_image)
            self.scene.scene().update()
            return 1

        if event.button() == Qt.RightButton:
            boxes_to_interact: list[UAnnotationBox] = []
            selected = self.scene.scene().selectedItems()
            for item in selected:
                if not isinstance(item, UAnnotationBox):
                    continue
                boxes_to_interact.append(item)

            if len(boxes_to_interact) <= 0:
                return

            menu_actions = [
                ("Преобразовать боксы в маски", lambda: [self.scene.remake_box_to_mask(box) for box in boxes_to_interact]),
            ]

            self.create_contex_menu(event, menu_actions)

    def on_release_mouse(self, event):
        return

    def on_key_press(self, event):
        if event.key() == Qt.Key_Shift:
            selected = [ item for item in self.scene.scene().selectedItems() if isinstance(item, UAnnotationMask)]
            if len(selected) > 0:
                self.last_mask = max(selected, key=lambda item: item.zValue())
            else:
                self.last_mask = None

            if self.last_mask:
                self.mask_adding_point_mode = True
                QApplication.setOverrideCursor(Qt.CrossCursor)
        if event.key() == Qt.Key_Delete:
            selected = [ item for item in self.scene.scene().selectedItems() if isinstance(item, UAnnotationItem)]
            for item in selected:
                self.scene.handle_on_delete_annotation_item(item)

    def on_key_release(self, event):
        if event.key() == Qt.Key_Shift and self.mask_adding_point_mode:
            QApplication.restoreOverrideCursor()
            self.mask_adding_point_mode = False
            self.last_mask = None

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        self.last_mask = None
        return

    def create_contex_menu(self, event, menu_items):
        menu = QMenu(self.scene)

        for text, func in menu_items:
            action = menu.addAction(text)
            action.triggered.connect(func)

        menu.exec_(event.globalPos())


class UForceDragAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UGlobalSignalHolder):
        self.scene = scene
        self.commander = commander

        self.mode = EWorkMode.ForceDragMode
        self.previous_mode: Optional[EWorkMode] = None

        self.mask_adding_point_mode: bool = False

    def start_mode(self, prev_mode):
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.scene.setDragMode(QGraphicsView.ScrollHandDrag)
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()
        self.scene.setDragMode(QGraphicsView.NoDrag)
        return

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        return

    def on_move_mouse(self, event):
        return

    def on_press_mouse(self, event):
        return

    def on_release_mouse(self, event):
        return

    def on_key_release(self, event: QKeyEvent):
        return

    def on_key_press(self, event: QKeyEvent):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        return


class UBoxAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        self.scene = scene
        self.commander = commander

        self.current_rect: Optional[UAnnotationBox] = None
        self.start_point: Optional[QPointF] = None

        self.mode = EWorkMode.BoxAnnotationMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode):
        if prev_mode is self.mode:
            return
        self.scene.scene().clearSelection()
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.previous_mode = prev_mode
        return

    def end_mode(self, change_mode: EWorkMode):
        if self.mode is change_mode or change_mode is EWorkMode.ForceDragMode:
            return
        elif change_mode is EWorkMode.GettingResultsMode:
            if self.current_rect:
                self.current_rect.delete_item()
        else:
            self._clean_rect()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def refresh(self):
        self._clean_rect()
        return

    def on_press_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class()):
            return

        # Если в режиме сохранен какой-то прямоугольник, его необходимо оставить на сцене
        if self.current_rect and self.start_point:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.DragMode.value)
        # Создание нового прямоугольника
        elif not (self.current_rect and self.start_point):
            cursor_pos = self.scene.mapToScene(event.pos())
            self.start_point = self.scene.get_image().mapFromScene(cursor_pos)
            self.current_rect = self.scene.add_annotation_box(
                self.start_point.x(),
                self.start_point.y(),
                1,
                1,
                self.scene.get_current_class(),
            )

    def on_move_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class() and self.current_rect and self.start_point):
            return

        current_cursor_pos = self.scene.get_image().mapFromScene(self.scene.mapToScene(event.pos()))
        rect = QRectF(self.start_point, current_cursor_pos).normalized()
        self.current_rect.setRect(rect)

    def on_release_mouse(self, event):
        if not (self.scene.get_image() and self.scene.get_current_class() and self.current_rect and self.start_point):
            return

        if self.current_rect.get_square() < 25:
            self.current_rect.delete_item()
            return
        if self.commander:
            self.scene.emit_commander_to_add(self.current_rect.get_annotation_data())
            self.current_rect.setSelected(True)
            self._clean_rect()
            self.commander.change_work_mode.emit(EWorkMode.DragMode.value)

    def on_key_release(self, event: QKeyEvent):
        return

    def on_key_press(self, event: QKeyEvent):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, item: UAnnotationItem):
        if self.current_rect is item:
            self._clean_rect()
        return

    def _clean_rect(self):
        self.current_rect = None
        self.start_point = None


class UMaskAnnotationMode(UBaseAnnotationMode):
    def __init__(self, scene: 'UAnnotationGraphicsView', commander: UAnnotationSignalHolder):
        super().__init__()
        self.scene = scene
        self.commander = commander

        self.current_mask: Optional[UAnnotationMask] = None

        self.mode = EWorkMode.MaskAnnotationMode
        self.previous_mode: Optional[EWorkMode] = None

    def start_mode(self, prev_mode: EWorkMode):
        self.scene.scene().clearSelection()
        if prev_mode is self.mode:
            return
        for annotation in self.scene.get_annotations():
            annotation.disable_selection()
        self.previous_mode = prev_mode

    def end_mode(self, change_mode: EWorkMode):
        if change_mode in [EWorkMode.ForceDragMode, EWorkMode.MaskAnnotationMode]:
            return
        elif change_mode is EWorkMode.GettingResultsMode:
            if self.current_mask:
                self.current_mask.delete_item()
        else:
            if self.current_mask and not self.current_mask.is_closed():
                self.current_mask.delete_item()
        for annotation in self.scene.get_annotations():
            annotation.enable_selection()

    def refresh(self):
        if self.current_mask:
            self.current_mask.clear_graphic_points()
        self.current_mask = None

    def get_previous_mode(self) -> EWorkMode | None:
        return self.previous_mode

    def on_move_mouse(self, event: QMouseEvent):
        image = self.scene.get_image()
        if not self.current_mask or not image:
            return

        self.current_mask.move(get_clamped_pos(self.scene, event.pos(), image))
        self.scene.scene().update()

    def on_release_mouse(self, event: QMouseEvent):
        image, class_data = self.scene.get_image(), self.scene.get_current_class()
        if not image or not class_data:
            return

        if event.button() == Qt.LeftButton:
            cursor_pos_image = get_clamped_pos(self.scene, event.pos(), image)
            if not self.current_mask:
                self.scene.scene().clearSelection()
                self.current_mask = self.scene.add_annotation_mask(
                    [cursor_pos_image],
                    class_data
                )
                self.current_mask.disable_selection()
                self.current_mask.create_graphic_points()
            else:
                if self.current_mask.fix_point():
                    self.scene.emit_commander_to_add(self.current_mask.get_annotation_data())

                    self.current_mask.clear_graphic_points()
                    self.current_mask.setSelected(False)
                    self.current_mask = None

    def on_press_mouse(self, event: QMouseEvent):
        pass

    def on_key_release(self, event: QKeyEvent):
        return

    def on_key_press(self, event: QKeyEvent):
        return

    def on_select_item(self, item: UAnnotationItem):
        return

    def on_update_item(self, item: UAnnotationItem, prev: FAnnotationData, curr: FAnnotationData):
        return

    def on_delete_item(self, mask: UAnnotationItem):
        if self.current_mask is mask:
            self.current_mask = None