from os import listdir
from os.path import isfile, join
import glob

dataset_path = "E:/VirtualBox/Shared/Varan_dataset/"
dataset_txt = dataset_path + "dataset.txt"

test_labels = dataset_path + "test/labels/"
valid_labels = dataset_path + "valid/labels/"
train_labels = dataset_path + "train/labels/"


only_files = [f for f in listdir(dataset_path + "Images/") if isfile(join(dataset_path + "Images/", f))]

with open(dataset_txt, 'r+') as f:
    f.seek(0)
    for image_name in only_files:
        f.write("./Images/" + image_name + '\n')
    f.truncate()
