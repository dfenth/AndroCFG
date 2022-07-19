"""
Output the generated graph in various formats
"""
from structures import Graph
import random

def output_dotfile(graph, file_path):
    """Output the graph in digraph form (useful for visualisation with graphviz)
    Args:
        graph: Graph - The graph to output the structure of
        file_path: str - The path of the output dot file
    """
    node_def = ""
    edge_def = ""

    for graph_class in graph.classes:
        class_color = "#{}".format("".join(random.choice("0123456789abcedf") for _ in range(6))) # generate a random color per class for the nodes
        for class_methods in graph_class.methods:
            for basic_block in class_methods.basic_blocks:
                instructions = ["{}: {}".format(x.line_num, x.instruction.replace("$", "•").replace('"', "'")) for x in basic_block.instructions]
                instructions = "\l".join(instructions) + "\l" # \l for left alignment in the dotfile
                node_def += "{} [shape=box color=\"{}\" label=\"{}\"];\n".format(basic_block.block_id, class_color, instructions)

                for target in basic_block.child_block_ids:
                    edge_def += "{} -> {};\n".format(basic_block.block_id, target)

    dot_data = "digraph {\n"
    dot_data += node_def
    dot_data += edge_def
    dot_data += "}\n"

    with open(file_path, "w") as dotfile:
        dotfile.write(dot_data)


