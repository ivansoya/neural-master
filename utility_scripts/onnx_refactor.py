from typing import Optional

import onnx
from ultralytics import YOLO
from onnx import helper, ModelProto, TensorProto, NodeProto, GraphProto, ValueInfoProto


def get_tensor_shape(model, tensor_name):
    for vi in model.graph.value_info:
        if vi.name == tensor_name:
            return [dim.dim_value for dim in vi.type.tensor_type.shape.dim]
    return None

def compute_concat_output_shape(input_shapes: list[list[int]], axis: int) -> list[int]:
    if not input_shapes:
        raise ValueError("Список input_shapes пуст.")

    rank = len(input_shapes[0])
    if any(len(shape) != rank for shape in input_shapes):
        raise ValueError("Все входные тензоры должны иметь одинаковую ранговость.")

    output_shape = input_shapes[0][:]  # копия формы первого

    for shape in input_shapes[1:]:
        for dim in range(rank):
            if dim == axis:
                output_shape[dim] += shape[dim]
            else:
                if output_shape[dim] != shape[dim]:
                    raise ValueError(f"Несовместимые размеры по оси {dim}: {output_shape[dim]} vs {shape[dim]}")
    return output_shape

def replace_conv_with_conv_sigmoid(model, target_names):
    graph = model.graph

    new_nodes = []
    for node in graph.node:
        if node.name in target_names and node.op_type == "Conv":
            print(f"Change {node.name} (Conv → ConvSigmoid)")

            conv_output = helper.make_tensor_value_info(
                node.output[0] + "_conv",
                onnx.TensorProto.FLOAT,
                get_tensor_shape(model, node.output[0])
            )
            new_conv = helper.make_node(
                "Conv",
                inputs=node.input,
                outputs=[conv_output.name],
                name=node.name
            )
            for attr in node.attribute:
                new_conv.attribute.extend([attr])

            sigmoid_output = node.output[0]
            new_sigmoid = helper.make_node(
                "Sigmoid",
                inputs=[conv_output.name],
                outputs=[sigmoid_output],
                name=node.name + "_sigmoid"
            )
            new_nodes.extend([new_conv, new_sigmoid])
            graph.value_info.extend([conv_output])
        else:
            new_nodes.append(node)

    graph.ClearField("node")
    graph.node.extend(new_nodes)

def remove_nodes_and_dependents(model: ModelProto, start_node_names: list[str]):
    # Построим карту: output_name → node
    output_to_node = {}
    name_to_node = {}

    for node in model.graph.node:
        name_to_node[node.name] = node
        for output in node.output:
            output_to_node[output] = node

    # Рекурсивный обход зависимых нод
    to_remove_names = set()

    def dfs_remove(node_name):
        if node_name not in name_to_node or node_name in to_remove_names:
            return
        node = name_to_node[node_name]
        to_remove_names.add(node_name)

        # Найти все ноды, у которых входы используют выходы текущего
        for output in node.output:
            for other_node in model.graph.node:
                if other_node.name in to_remove_names:
                    continue
                if output in other_node.input:
                    dfs_remove(other_node.name)

    # Запустить обход для всех стартовых нодов
    for node_name in start_node_names:
        dfs_remove(node_name)

    # Фильтруем список
    remaining_nodes = [node for node in model.graph.node if node.name not in to_remove_names]

    # Очищаем граф и добавляем обратно только оставшиеся ноды
    del model.graph.node[:]
    model.graph.node.extend(remaining_nodes)

    return model

def remove_outputs_by_name(model: ModelProto, output_names_to_remove: list[str]) -> ModelProto:
    remaining_outputs = [out for out in model.graph.output if out.name not in output_names_to_remove]

    del model.graph.output[:]
    model.graph.output.extend(remaining_outputs)

    return model

def rename_outputs(model: ModelProto, outputs: dict[str, str]) -> ModelProto:
    for output in model.graph.output:
        if output.name in outputs:
            output.name = outputs[output.name]

    for node in model.graph.node:
        for i, out_name in enumerate(node.output):
            if out_name in outputs:
                node.output[i] = outputs[out_name]

    return model

def add_concat_nodes(
        model: ModelProto,
        concat_descriptions: list[dict],
) -> ModelProto:

    for desc in concat_descriptions:
        input_names = desc["inputs"]
        output = desc["output"]
        name = desc["name"]
        axis = desc.get("axis", 1)  # по умолчанию объединяем по оси 1

        concat_node = helper.make_node(
            'Concat',
            inputs=input_names,
            outputs=[output],
            axis=axis,
            name=name
        )

        input_shapes = [get_tensor_shape(model, input_names[i]) for i in range(len(input_names))]
        output_shape = compute_concat_output_shape(input_shapes, axis)

        model.graph.output.append(
            helper.make_tensor_value_info(output, TensorProto.FLOAT, output_shape)
        )

        model.graph.node.append(concat_node)

    return model


def topological_sort_nodes(nodes):
    # nodes: список onnx.NodeProto
    name_to_node = {node.name: node for node in nodes}
    # Построим граф зависимостей по выходам/входам
    # Узлы — ноды, ребра — "node A -> node B", если output A входит в input B

    # Считаем сколько входов каждой ноды зависит от других нод в списке
    input_to_nodes = {}
    in_degree = {node.name: 0 for node in nodes}

    # Map output tensor -> node producing его
    output_to_node_name = {}
    for node in nodes:
        for out in node.output:
            output_to_node_name[out] = node.name

    for node in nodes:
        for inp in node.input:
            producer = output_to_node_name.get(inp, None)
            if producer and producer in in_degree:
                in_degree[node.name] += 1
                input_to_nodes.setdefault(producer, []).append(node.name)

    # Очередь нод с in_degree=0
    queue = [name for name, deg in in_degree.items() if deg == 0]
    sorted_nodes = []
    while queue:
        current = queue.pop(0)
        sorted_nodes.append(name_to_node[current])
        for dependent in input_to_nodes.get(current, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(sorted_nodes) != len(nodes):
        raise RuntimeError("Цикл в графе нод, топологическая сортировка невозможна")

    return sorted_nodes

def remove_nodes_after(model: ModelProto, keep_node_names: list[str]):
    graph = model.graph

    stop_outputs = set()
    for node in graph.node:
        if node.name in keep_node_names:
            stop_outputs.update(node.output)

    needed_nodes = []
    visited_outputs = set(stop_outputs)
    added = True

    while added:
        added = False
        for node in graph.node:
            if node in needed_nodes:
                continue
            if any(output in visited_outputs for output in node.output):
                needed_nodes.append(node)
                visited_outputs.update(node.input)
                added = True

    # Топологическая сортировка нужных нод
    needed_nodes = topological_sort_nodes(needed_nodes)

    needed_node_names = set(n.name for n in needed_nodes)
    graph.ClearField("node")
    graph.node.extend(needed_nodes)

    graph.ClearField("output")

def find_value_info_by_name(graph, name: str) -> Optional[ValueInfoProto]:
    for value_info in list(graph.value_info) + list(graph.input) + list(graph.output):
        if value_info.name == name:
            return value_info
    return None

def add_model_outputs(model: ModelProto, output_names: list[str], node_output_names: list[str]):
    existing_output_names = set(o.name for o in model.graph.output)

    for tensor_name in node_output_names:
        if tensor_name in existing_output_names:
            continue

        value_info = find_value_info_by_name(model.graph, tensor_name)
        if value_info is None:
            new_output = helper.make_tensor_value_info(
                name=tensor_name,
                elem_type=TensorProto.FLOAT,
                shape=None
            )
        else:
            new_output = helper.make_tensor_value_info(
                name=tensor_name,
                elem_type=value_info.type.tensor_type.elem_type,
                shape=[d.dim_value if (d.dim_value > 0) else None for d in value_info.type.tensor_type.shape.dim]
            )
        model.graph.output.append(new_output)

def refactor_seg_yolov11_model(model_path: str, save_model_path: str):
    start_model = onnx.load(model_path)

    refactor_model = remove_outputs_by_name(start_model, ["output0"])

    refactor_model = rename_outputs(refactor_model, {"output1": "proto_masks"})

    refactor_model = remove_nodes_and_dependents(
        refactor_model,
        ["/model.23/Reshape", "/model.23/Reshape_1", "/model.23/Reshape_2", "/model.23/Concat_3", "/model.23/Concat_2", "/model.23/Concat_1"]
    )

    replace_conv_with_conv_sigmoid(
        refactor_model,
        ["/model.23/cv3.0/cv3.0.2/Conv", "/model.23/cv3.1/cv3.1.2/Conv", "/model.23/cv3.2/cv3.2.2/Conv"]
    )

    refactor_model = add_concat_nodes(refactor_model, [
        {
            "inputs" : ["/model.23/cv3.2/cv3.2.2/Conv_output_0", "/model.23/cv2.2/cv2.2.2/Conv_output_0", "/model.23/cv4.2/cv4.2.2/Conv_output_0"],
            "output": "tensor_20",
            "name": "/model.23/Concat_1",
            "axis": 1
        }, {
            "inputs": ["/model.23/cv3.1/cv3.1.2/Conv_output_0", "/model.23/cv2.1/cv2.1.2/Conv_output_0", "/model.23/cv4.1/cv4.1.2/Conv_output_0"],
            "output": "tensor_40",
            "name": "/model.23/Concat_2",
            "axis": 1
        }, {
            "inputs": ["/model.23/cv3.0/cv3.0.2/Conv_output_0", "/model.23/cv2.0/cv2.0.2/Conv_output_0", "/model.23/cv4.0/cv4.0.2/Conv_output_0"],
            "output": "tensor_80",
            "name": "/model.23/Concat_3",
            "axis": 1
        }
    ])

    onnx.save(refactor_model, save_model_path)

def refactor_detect_yolov11_model(model_path: str, save_model_path: str):
    refactor_model = onnx.load(model_path)

    remove_nodes_after(
        refactor_model,
        ["/model.23/Concat", "/model.23/Concat_1", "/model.23/Concat_2"]
    )

    replace_conv_with_conv_sigmoid(
        refactor_model,
        ["/model.23/cv3.0/cv3.0.2/Conv", "/model.23/cv3.1/cv3.1.2/Conv", "/model.23/cv3.2/cv3.2.2/Conv"]
    )

    add_model_outputs(
        refactor_model,
        ["tensor_20_out", "tensor_40_out", "tensor_80_out"],
        ["/model.23/Concat_output_0", "/model.23/Concat_1_output_0", "/model.23/Concat_2_output_0"]
    )

    onnx.save(refactor_model, save_model_path)


def refactor_with_version_yolo(yolo_version: str, model_path: str, save_model_path: str) -> bool:
    try:
        if yolo_version == "yolov11-seg":
            refactor_seg_yolov11_model(model_path, save_model_path)
        elif yolo_version == "yolov11":
            refactor_detect_yolov11_model(model_path, save_model_path)
        else:
            print(f"ОШИБКА: Нет реализации рефактора для модели {yolo_version}!")
            return False
    except Exception as error:
        print(str(error))
        return False

if __name__ == "__main__":
    refactor_detect_yolov11_model("C:/Users/1/Documents/PycharmProjects/neural-master/untrained/yolo11n.onnx",
                               "C:/Users/1/Documents/PycharmProjects/neural-master/untrained/trimmed_model.onnx")

