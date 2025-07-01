from PyQt5.QtCore import QObject, pyqtSignal, QThread

class UTaskRunner(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, tasks: list[tuple[callable, tuple, dict]]):
        """
        tasks — список из кортежей: (функция, позиционные_аргументы, именованные_аргументы)

        Пример:
            [
                (print, ("Hello",), {}),
                (some_func, (1, 2), {"debug": True})
            ]
        """
        super().__init__()
        self.tasks = tasks

    def run(self):
        self.started.emit()
        for func, args, kwargs in self.tasks:
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"Ошибка при выполнении {func.__name__}: {e}")
        self.finished.emit()