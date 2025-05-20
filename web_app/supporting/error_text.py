

class UErrorsText:

    @staticmethod
    def not_existing_type_dataset(function_name: str, type_t: str):
        return f"Ошибка в {function_name}! Не существует такого типа датасетов {type_t}!"

    @staticmethod
    def not_existing_dataset_in_project(function_name: str, dataset: str):
        return f"Ошибка в {function_name}! В проекте отсутствует датасет {dataset}!"

    @staticmethod
    def not_existing_path_to_dataset(function_name: str, dataset_path: str):
        return f"Ошибка в {function_name}! Не существует датасета по пути {dataset_path}!"

    @staticmethod
    def not_existing_annotations(function_name: str, dataset: str):
        return f"Ошибка в {function_name}! В проекте нет аннотаций для датасета {dataset}!"

    @staticmethod
    def annotations_already_exist(function_name: str, dataset: str):
        return f"Ошибка в {function_name}! В проекте уже есть аннотации в датасете {dataset}!"

    @staticmethod
    def not_existing_annotation_in_dataset(function_name: str, dataset: str):
        return f"Ошибка в {function_name}! В датасете {dataset} не существует переданной в функцию {function_name} аннотации!"

    @staticmethod
    def type_swap_is_equal(function_name: str):
        return f"Ошибка в {function_name}! Указанный тип датасетов для свапа указан одинаковым!"