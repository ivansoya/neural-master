import os
from ftplib import FTP, error_perm, error_temp, error_proto, error_reply

import argparse
from tqdm import tqdm

HOST = "172.25.78.214"
USER = "voran"
PASSWORD = "x2Wv+Vb<n08n!Do_tE"
PORT = 21
REMOTE_FOLDER = "/varan"
SAVE_LOG_FOLDER = "save_logs"
TIMEOUT = 60

class NoImageException(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code

def create_ftp_connection(host, user, password, port, timeout, retries=3):
    for attempt in range(1, retries + 1):
        try:
            print(f"Attempting to connect to FTP ({attempt}/{retries})...")
            ftp = FTP(timeout=timeout)
            ftp.connect(host, int(port))
            ftp.login(user=user, passwd=password)
            print("Successful connection to the FTP server.")
            return ftp
        except (error_perm, error_temp, error_proto, error_reply) as e:
            print(f"FTP Error: {e}")
        except Exception as e:
            print(f"General Error: {e}")

    raise ConnectionError("Failed to connect to the FTP server after several attempts.")

def safe_close_ftp(ftp):
    if ftp:
        try:
            ftp.quit()  # Корректное завершение
        except Exception as e:
            print(f"Error with Quit: {e}")
            try:
                ftp.close()  # Аварийное завершение
                print("Connection closed with ftp.close().")
            except Exception as close_error:
                print(f"FTP connection has already closed!: {close_error}")
    else:
        print("FTP connection has already closed!")


def get_to_remote_folder(ftp, remote_folder):
    try:
        ftp.cwd(remote_folder)
    except error_perm:
        try:
            ftp.mkd(remote_folder)
            ftp.cwd(remote_folder)
            print(f"The {remote_folder} folder has been created and set as the current folder.")
        except Exception as e:
            raise ConnectionError(f"Failed to create or navigate to the {remote_folder} folder: {e}")
    except Exception as e:
        raise ConnectionError(f"Error accessing the {remote_folder} folder: {e}")


def list_directories(ftp, path):
    directories = []
    def callback(line):
        parts = line.split()
        if len(parts) > 0 and parts[0].startswith('d'):
            directories.append(parts[-1])  # Последний элемент строки - имя файла/папки
            print(parts[-1])
    try:
        ftp.cwd(path)  # Переход к указанному пути
        ftp.retrlines('LIST', callback)  # Считываем содержимое директории с помощью команды LIST
        return directories

    except Exception as e:
        print(f"Ошибка: {e}")
        return None

def is_image_file(filename):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    return any(filename.lower().endswith(ext) for ext in image_extensions)

def start_download(ftp, directories, arguments):

    if not os.path.exists(os.path.join(arguments.path, SAVE_LOG_FOLDER)):
        os.mkdir(os.path.join(arguments.path, SAVE_LOG_FOLDER))

    print("Обнаружено всего ", len(directories), " директорий с изображениями на сервере!")
    for folder in directories:
        print("Начата выгрузка изображений из папки ", folder)
        local_path_folder = os.path.join(arguments.path, folder)
        if not os.path.exists(local_path_folder):
            os.makedirs(local_path_folder)

        # Проверяем, есть ли файл для записи логов
        log_file_path = os.path.join(arguments.path, SAVE_LOG_FOLDER) + '\\' + folder + '.txt'
        if not os.path.exists(log_file_path):
            with open(log_file_path, 'w') as log_file:
                pass

        with open(log_file_path, 'a+') as textlog:
            existing_files = textlog.readlines()

            ftp.cwd(REMOTE_FOLDER + '/' + folder)
            content = ftp.nlst()

            for i in tqdm(range(len(content)), desc="Download Progress", ncols=100):
                if is_image_file(content[i]):
                    # Загружаем картинку в локальную папку
                    if not content[i] in existing_files:
                        with open(os.path.join(local_path_folder, content[i]), 'wb') as save_image:
                            ftp.retrbinary(f"RETR {content[i].strip()}", save_image.write)

                        # Записываем в конец файла название скачанного изображения
                        textlog.write(content[i] + '\n')

                    if arguments.delete is True:
                        ftp.delete(content[i])

def main():
    download_complete = False
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--path', type=str, help="Локальный путь для загрузки", required=True)
    parser.add_argument('-d', '--delete', action='store_true', help="Удалять ли скачанные изображения с сервера?")

    args = parser.parse_args()

    ftp = None
    while download_complete is False:
        try:
            ftp = create_ftp_connection(
                HOST,
                USER,
                PASSWORD,
                PORT,
                TIMEOUT
            )

            remote_dirs = list_directories(ftp, REMOTE_FOLDER)

            start_download(ftp, remote_dirs, args)

            ftp.quit()

            # Успешное завершение цикла
            download_complete = True
            continue

        except ConnectionError as e:
            print(f"Error with connection: {e}")
            safe_close_ftp(ftp)
            continue

        except Exception as e:
            print(f"Error: {e}")
            safe_close_ftp(ftp)
            continue

if __name__ == "__main__":
    main()
