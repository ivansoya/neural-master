from pycocotools.coco import COCO

try:
    coco = COCO("C:/Users/1/Documents/Проект Варан/KGT_Test/coco.json")  # путь до твоего COCO JSON
    print("COCO JSON валиден!")
except Exception as e:
    print("Ошибка в COCO JSON:", e)