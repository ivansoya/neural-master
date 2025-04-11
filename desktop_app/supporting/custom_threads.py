from PyQt5.QtCore import QThread, pyqtSignal

class UProgressThread(QThread):
    signal_on_process_item = pyqtSignal(int, int, object)
    signal_on_finish = pyqtSignal(tuple)

    def __init__(self, data_list: list, func: callable, *args, **kwargs):
        super().__init__()

        self.data_list = data_list
        self.count = len(self.data_list)
        self.args = args
        self.kwargs = kwargs

        self.process_func = func
        self.finish_params = tuple()

        self._is_running = True

    def run(self):
        for index in range(len(self.data_list)):
            if not self._is_running:
                break
            item = self.data_list[index]
            self.process_func(item, *self.args)
            self.signal_on_process_item.emit(index, self.count, item)
        self.signal_on_finish.emit(self.finish_params)

    def stop(self):
        self._is_running = False

    def set_finish_params(self, params: tuple):
        self.finish_params = params