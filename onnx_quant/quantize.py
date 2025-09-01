import onnx
import torch
from onnx import shape_inference
from ultralytics import YOLO
from onnxruntime.quantization import (
    quantize_static,
    CalibrationDataReader,
    QuantType,
    QuantFormat,
    QuantizationMode
)
from pathlib import Path
from PIL import Image
import numpy as np

# -----------------------------
# 1. Настройки
# -----------------------------
MODEL_PATH = r"C:\Quantizing\varan11n_sgd_12c.pt"       # Путь к твоей PyTorch модели
ONNX_FP32_PATH = r"C:\Quantizing\varan11n_sgd_12c.onnx"    # Куда сохранить ONNX float32
ONNX_INT8_PATH = r"C:\Users\1\Documents\Проект Варан\Обучение\Обученные модели\2025.08.28\varan11n_sgd_12c_int8.onnx"    # Куда сохранить INT8 ONNX
INPUT_SIZE = (640, 640)              # Размер входа модели (HW)
CALIBRATION_IMAGES_DIR = r"C:\Users\1\Documents\Проект Варан\Датасеты для обучения\train_2025.08.28\images" # Папка с калибровочными изображениями (500-1000)

BATCH_SIZE = 1                        # Для калибровки
NUM_CALIBRATION_IMAGES = 500          # Сколько картинок взять для калибровки

# -----------------------------
# 2. Экспорт модели в ONNX
# -----------------------------
model = YOLO(MODEL_PATH)   # Загрузка PyTorch модели

model.export(
    format="onnx",
    opset=17,
    simplify=True,
    dynamic=False,  # фиксированный размер входа
    verbose=True
)
print("ONNX модель создана:", ONNX_FP32_PATH)

# -----------------------------
# 3. Создаем CalibrationDataReader
# -----------------------------
class YoloCalibrationReader(CalibrationDataReader):
    def __init__(self, img_dir, input_size=(640,640), max_imgs=500):
        self.img_paths = list(Path(img_dir).glob("*.*"))[:max_imgs]
        self.input_size = input_size
        self.enum_data = iter(self._generator())

    def _preprocess(self, img_path):
        img = Image.open(img_path).convert("RGB")
        img = img.resize(self.input_size)
        img = np.array(img).astype(np.float32) / 255.0
        img = np.transpose(img, (2,0,1))  # HWC -> CHW
        img = np.expand_dims(img, axis=0)  # 1xCxHxW
        return img

    def _generator(self):
        for p in self.img_paths:
            yield {"images": self._preprocess(p)}

    def get_next(self):
        try:
            return next(self.enum_data)
        except StopIteration:
            return None

calib_reader = YoloCalibrationReader(CALIBRATION_IMAGES_DIR, INPUT_SIZE, NUM_CALIBRATION_IMAGES)

# -----------------------------
# 4. Квантование в INT8
# -----------------------------

quantize_static(
    model_input=ONNX_FP32_PATH,
    model_output=ONNX_INT8_PATH,
    calibration_data_reader=calib_reader,
    quant_format=QuantFormat.QOperator,
    activation_type=QuantType.QInt8,
    weight_type=QuantType.QInt8,
    per_channel=True,
    reduce_range=False,
)

print("INT8 ONNX saved:", ONNX_INT8_PATH)

# -----------------------------
# 5. Дальше: можно использовать ONNX_INT8 для RKNN
# -----------------------------
print("Готово! Теперь INT8 ONNX можно конвертировать в RKNN.")
