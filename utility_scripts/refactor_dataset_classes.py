import os, glob

dataset_path = "E:/neural_networks/Обучение Варана/dataset/"
dataset_yaml = dataset_path + "data.yaml"

test_labels = dataset_path + "test/labels/"
valid_labels = dataset_path + "valid/labels/"
train_labels = dataset_path + "train/labels/"

classes_raw = ("#Names\n"
               "names:\n"
               "  0: narrow-grab\n"
               "  1: big-grab\n"
               "  2: narrow-bucket\n"
               "  3: big-bucket\n"
               "  4: hook\n"
               #"  5: narrow-grab\n"
               #"  6: rail\n"
               #"  7: rubble\n"
               #"  8: sleeper\n"
               "\n"
               )
# Правило рефактора, заменяет левое значение id в файлах labels на правое значение
refactor_label_rule = {
    '0': '0',
#    '1': '3',
#    '2': '5',
}

def restruct_file_labels(path):
    for filename in glob.glob(path + "*.txt"):
        with open(filename, 'r+') as f:
            d = f.readlines()
            f.seek(0)
            for line in d:
                separ_list = line.split(' ')
                if separ_list[0] in list(refactor_label_rule.keys()):
                    str_new = refactor_label_rule[separ_list[0]]
                    for token in separ_list[1:]:
                        str_new += " " + str(token)
                    f.write(str_new)
                else:
                    f.write(line)
            f.truncate()

def run():
    # Обработка файла data.yaml
    with open(dataset_yaml, "r+") as f:
        d = f.readlines()
        f.seek(0)
        t = 0
        for line in d:
            if "nc:" in line:
                t = 1
            if "roboflow:" in line:
                for class_raw in classes_raw:
                    f.write(class_raw)
                t = 0
            if t == 0:
                f.write(line)
            if t == 1:
                continue
        f.truncate()

    restruct_file_labels(test_labels)
    restruct_file_labels(valid_labels)
    restruct_file_labels(train_labels)

run()
