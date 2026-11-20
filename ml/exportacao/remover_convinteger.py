"""Substitui o único ConvInteger (patch embedding conv_proj) por Conv em float32.

Motivo: o runtime Android do ONNX Runtime (build mobile reduzido) não tem kernel
para ConvInteger(10): "Could not find an implementation for ConvInteger(10)".
Equivalência: ConvInteger(x_q - zp_x, w_q - zp_w) * (s_x * s_w) = Conv(x_deq, w_deq),
com x_deq = (x_q - zp_x) * s_x e w_deq = (w_q - zp_w) * s_w. Nomes e demais nós intactos.
Uso: python3 -I remover_convinteger.py entrada.onnx saida.onnx
"""
import sys
import numpy as np
import onnx
from onnx import helper, numpy_helper, TensorProto

src, dst = sys.argv[1], sys.argv[2]
m = onnx.load(src)
g = m.graph
init = {t.name: t for t in g.initializer}

conv = [n for n in g.node if n.op_type == "ConvInteger"]
assert len(conv) == 1, f"esperado 1 ConvInteger, achei {len(conv)}"
cn = conv[0]
x_q, w_q, x_zp, w_zp = cn.input
out_int = cn.output[0]

# nós a remover: ConvInteger, Cast e Mul de escala logo após
cast = [n for n in g.node if n.op_type == "Cast" and n.input[0] == out_int]
assert len(cast) == 1
cast = cast[0]
mul = [n for n in g.node if n.op_type == "Mul" and n.input[0] == cast.output[0]]
assert len(mul) == 1
mul = mul[0]
final_out = mul.output[0]  # '/conv_proj/Conv_output_0quant_scaled_output' (consumido pelo Add do bias)

# escala de entrada: sai de imagem_QuantizeLinear (DynamicQuantizeLinear)
dq_in = [n for n in g.node if n.op_type == "DynamicQuantizeLinear" and n.output[0] == x_q]
assert len(dq_in) == 1
x_scale, x_zp_out = dq_in[0].output[1], dq_in[0].output[2]
assert x_zp_out == x_zp, "zero-point de entrada diverge"

# pesos dequantizados em float32 (zero-point de pesos = 0 e escala por tensor)
w_scale = cn_w_scale = "conv_proj.weight_scale"
w = numpy_helper.to_array(init[w_q]).astype(np.float32)
w_zp_arr = numpy_helper.to_array(init[w_zp]).astype(np.float32)
w_s = numpy_helper.to_array(init[w_scale]).astype(np.float32)
assert np.all(w_zp_arr == 0), "zero-point de pesos não é zero; caso não previsto"
w_f = (w - w_zp_arr) * w_s
w_f_name = "conv_proj.weight_float32"
g.initializer.append(numpy_helper.from_array(w_f.astype(np.float32), name=w_f_name))

# entrada dequantizada: DequantizeLinear(x_q, x_scale, x_zp)
x_f = "conv_proj_input_dequant"
dq_node = helper.make_node("DequantizeLinear", [x_q, x_scale, x_zp], [x_f], name="/conv_proj/input_dequant")

conv_node = helper.make_node(
    "Conv", [x_f, w_f_name], [final_out], name="/conv_proj/Conv_float",
    dilations=[1, 1], group=1, kernel_shape=[16, 16], pads=[0, 0, 0, 0], strides=[16, 16],
)

new_nodes = []
for n in g.node:
    if n is cn:
        new_nodes.append(dq_node)
        new_nodes.append(conv_node)
    elif n is cast or n is mul:
        continue
    else:
        new_nodes.append(n)
del g.node[:]
g.node.extend(new_nodes)

# remove inicializadores órfãos da antiga conv inteira (somente se não usados)
used = {i for n in g.node for i in n.input}
keep = [t for t in g.initializer if t.name in used or t.name == w_f_name]
del g.initializer[:]
g.initializer.extend(keep)

onnx.checker.check_model(m)
onnx.save(m, dst)
print("ok", dst)
print("ConvInteger restantes:", sum(n.op_type == "ConvInteger" for n in onnx.load(dst).graph.node))
