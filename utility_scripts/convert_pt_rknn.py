import os
import sys
import onnx
from onnx import helper
from ultralytics import YOLO
from rknn.api import RKNN

DATASET_PATH = "/home/voran/voran-ftp-sync/training/export/dataset.txt"
DEFAULT_QUANT = True
# yolov11
REFACTOR_LAYER_NAMES = ["/model.23/Concat_2", "/model.23/Concat_1", "/model.23/Concat"]
CONV_REPLACE_NAMES = ["/model.23/cv3.2/cv3.2.2/Conv", "/model.23/cv3.1/cv3.1.2/Conv", "/model.23/cv3.0/cv3.0.2/Conv"]
# yolov8
#REFACTOR_LAYER_NAMES = ["/model.22/Concat_2", "/model.22/Concat_1", "/model.22/Concat"]
#CONV_REPLACE_NAMES = ["/model.22/cv3.2/cv3.2.2/Conv", "/model.22/cv3.1/cv3.1.2/Conv", "/model.22/cv3.0/cv3.0.2/Conv"]

def get_tensor_shape(model, tensor_name):
    for vi in model.graph.value_info:
        if vi.name == tensor_name:
            return [dim.dim_value for dim in vi.type.tensor_type.shape.dim]
    return None

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

def trim_onnx_after_layers(model, output_layer_names):
    graph = model.graph
    nodes = graph.node

    all_inputs = {inp.name for inp in graph.input}

    new_nodes = []
    found_outputs = set(output_layer_names)
    valid_outputs = []

    for node in nodes:
        new_nodes.append(node)
        if node.name in found_outputs:
            print(f"Cut nodes after {node.name}")
            found_outputs.remove(node.name)

            for out_tensor in node.output:
                if out_tensor not in all_inputs:
                    shape = get_tensor_shape(model, out_tensor)
                    valid_outputs.append(helper.make_tensor_value_info(
                        out_tensor, onnx.TensorProto.FLOAT, shape))

            if not found_outputs:
                break

    graph.ClearField("output")
    graph.output.extend(valid_outputs)

    graph.ClearField("node")
    graph.node.extend(new_nodes)

def parse_arg():
    if len(sys.argv) < 3:
        print("Usage: python3 {} pytorch_model_path [platform] [dtype(optional)] [output_rknn_path(optional)]".format(sys.argv[0]));
        print("       platform choose from [rk3562,rk3566,rk3568,rk3576,rk3588,rk1808,rv1109,rv1126]")
        print("       dtype choose from [i8, fp] for [rk3562,rk3566,rk3568,rk3576,rk3588]")
        print("       dtype choose from [u8, fp] for [rk1808,rv1109,rv1126]")
        exit(1)

    model_path = sys.argv[1]
    platform = sys.argv[2]

    do_quant = DEFAULT_QUANT
    if not model_path.endswith(".pt"):
        print(f"ERROR: Invalid model format: {model_path}! Needs PyTorch format!")
        exit(1)
    if len(sys.argv) > 3:
        model_type = sys.argv[3]
        if model_type not in ['i8', 'u8', 'fp']:
            print("ERROR: Invalid model type: {}".format(model_type))
            exit(1)
        elif model_type in ['i8', 'u8']:
            do_quant = True
        else:
            do_quant = False

    if len(sys.argv) > 4:
        output_path = sys.argv[4]
    else:
        output_path = model_path.replace(".pt", ".rknn")

    return model_path, platform, do_quant, output_path

def main():
    model_path, platform, do_quant, output_path = parse_arg()

    model = YOLO(model_path)

    print("--> Converting PyToch model to Onnx!")
    onnx_model_path = model.export(format="onnx")
    print("done!")

    onnx_optimized_format = onnx_model_path.replace(".onnx", "_ref.onnx")
    print("--> Refactoring Onnx model to rknn optimized format!")
    model_onnx = onnx.load(onnx_model_path)
    trim_onnx_after_layers(model_onnx, REFACTOR_LAYER_NAMES)
    if platform == "rk3566":
        replace_conv_with_conv_sigmoid(model_onnx, CONV_REPLACE_NAMES)
    else:
        print("Platform is not rk3566, there are is no changes to do!")
    onnx.save(model_onnx, onnx_optimized_format)
    print(f"done!")
    os.remove(onnx_model_path)

    # Create RKNN object
    rknn = RKNN(verbose=False)

    # Pre-process config
    print('--> Config model')
    rknn.config(mean_values=[[0, 0, 0]], std_values=[
        [255, 255, 255]], target_platform=platform, quantized_algorithm="normal")
    print('done')

    # Load model
    print('--> Loading model')
    ret = rknn.load_onnx(model=onnx_optimized_format)
    if ret != 0:
        print('Load model failed!')
        exit(ret)
    print('done')

    # Build model
    print('--> Building model')
    ret = rknn.build(do_quantization=do_quant, dataset=DATASET_PATH)
    if ret != 0:
        print('Build model failed!')
        exit(ret)
    print('done')

    # Export rknn model
    print('--> Export rknn model')
    ret = rknn.export_rknn(output_path)
    if ret != 0:
        print('Export rknn model failed!')
        exit(ret)
    print('done')

    # Release
    rknn.release()
    # Delete refactor onnx
    os.remove(onnx_optimized_format)

if __name__ == "__main__":
    main()
