import os
import sys
from onnx_refactor import refactor_with_version_yolo
from ultralytics import YOLO
from rknn.api import RKNN

DATASET_PATH = "/home/voran/voran-ftp-sync/training/export/dataset.txt"
DEFAULT_QUANT = True

def parse_arg():
    if len(sys.argv) < 3:
        print("Использование: python3 {} путь_к_модели_pytorch [yolo_версия] [платформа] [тип_данных(необязательно)] [путь_к_выходному_rknn(необязательно)]".format(sys.argv[0]))
        print("       версия yolo: выберите из [yolov11-seg]")
        print("       платформа: выберите из [rk3562, rk3566, rk3568, rk3576, rk3588, rk1808, rv1109, rv1126]")
        print("       тип данных: [i8, fp] для [rk3562, rk3566, rk3568, rk3576, rk3588]")
        print("       тип данных: [u8, fp] для [rk1808, rv1109, rv1126]")
        exit(1)

    model_path = sys.argv[1]
    yolo_version = sys.argv[2]
    platform = sys.argv[3]

    do_quant = DEFAULT_QUANT
    if not model_path.endswith(".pt"):
        print(f"ОШИБКА: неверный формат модели: {model_path}! Требуется формат PyTorch (.pt)!")
        exit(1)
    if yolo_version not in ['yolov11-seg', 'yolov11']:
        print(f"ОШИБКА: неверная версия YOLO: {yolo_version}! Требуется одна из допустимых версий!")
        print("       версия yolo: выберите из [yolov11-seg]")
        exit(1)
    if len(sys.argv) > 4:
        model_type = sys.argv[4]
        if model_type not in ['i8', 'u8', 'fp']:
            print("ОШИБКА: неверный тип модели: {}".format(model_type))
            exit(1)
        elif model_type in ['i8', 'u8']:
            do_quant = True
        else:
            do_quant = False
    if len(sys.argv) > 5:
        output_path = sys.argv[5]
    else:
        output_path = model_path.replace(".pt", ".rknn")

    return model_path, yolo_version, platform, do_quant, output_path

def main():
    model_path, yolo_version, platform, do_quant, output_path = parse_arg()

    model = YOLO(model_path)

    print("--> Конвертация модели PyTorch в формат ONNX...")
    onnx_model_path = model.export(format="onnx")
    print("Конвертация завершена!")

    onnx_optimized_format = onnx_model_path.replace(".onnx", "_ref.onnx")
    print("--> Рефакторинг модели ONNX для поддержки квантования...")
    ret = refactor_with_version_yolo(yolo_version, onnx_model_path, onnx_optimized_format)
    if ret is False:
        print("--> Скрипт завершён с ошибкой!")
        exit(1)
    print("Рефакторинг завершён!")
    os.remove(onnx_model_path)

    # Создание объекта RKNN
    rknn = RKNN(verbose=False)

    # Конфигурация модели
    print('--> Конфигурация модели...')
    rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform=platform,
        quantized_dtype='w8a8',
        # optimization_level=0,
        quant_img_RGB2BGR=True,
    )
    print('Готово!')

    # Загрузка модели
    print('--> Загрузка модели...')
    ret = rknn.load_onnx(model=onnx_optimized_format)
    if ret != 0:
        print('Загрузка модели не удалась!')
        exit(ret)
    print('Готово!')

    # Компиляция модели
    print('--> Компиляция модели...')
    ret = rknn.build(do_quantization=do_quant, dataset=DATASET_PATH)
    if ret != 0:
        print('Компиляция модели не удалась!')
        exit(ret)
    print('Готово!')

    # Экспорт модели в формате RKNN
    print('--> Экспорт модели в формате RKNN...')
    ret = rknn.export_rknn(output_path)
    if ret != 0:
        print('Экспорт модели не удался!')
        exit(ret)
    print('Готово!')

    # Очистка ресурсов
    rknn.release()
    # Удаление промежуточного файла ONNX после рефакторинга
    os.remove(onnx_optimized_format)

if __name__ == "__main__":
    main()

