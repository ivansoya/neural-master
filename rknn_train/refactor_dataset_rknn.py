import os
from os.path import isfile
import random

dataset_path = "/home/voran/voran-ftp-sync/training/2025.07.16/"
dataset_txt = "/home/voran/voran-ftp-sync/training/export/dataset.txt"

images = os.path.join(dataset_path, "images").replace('\\', '/')
only_files = [os.path.join(images, f).replace('\\', '/') for f in os.listdir(images)
              if isfile(os.path.join(images, f).replace('\\', '/'))]

reduced_count = max(1, len(only_files) // 10)
only_files = random.sample(only_files, reduced_count)

with open(dataset_txt, 'w') as f:
    for image_name in only_files:
        f.write(f"{image_name}\n")

