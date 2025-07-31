from annotation.page_annotation import UTextInputDialog


def terminate_closable_dialog(keys_list: list[str]) -> str:
    dialog = UTextInputDialog()
    dialog.combo_choose_dataset.addItems(keys_list)
    dialog.combo_choose_dataset.currentTextChanged.connect(
        lambda selected_item: dialog.lineedit_dataset_name.setText(selected_item)
    )
    if dialog.exec_():
        return dialog.lineedit_dataset_name.text()