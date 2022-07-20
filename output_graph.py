"""
Output the generated graph in various formats
"""
from structures import Graph
import random

def output_cfg_dotfile(graph, file_path):
    """Output the CFG in digraph form (useful for visualisation with graphviz)
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


def output_fcg_dotfile(graph, file_path):
    """Output the FCG in digraph form (useful for visualisation with graphviz)
    Args:
        graph: Graph - The graph to output the structure of
        file_path: str - The path of the output dot file
    """
    node_def = ""
    edge_def = ""

    for graph_class in graph.classes:
        class_color = "#{}".format("".join(random.choice("0123456789abcedf") for _ in range(6))) # generate a random color per class for the nodes
        for class_method in graph_class.methods:
            node_def += "{} [shape=box color=\"{}\" label=\"{}\"];\n".format(class_method.method_id, class_color, class_method.method_name)
            
            for target in class_method.calls_out:
                edge_def += "{} -> {};\n".format(class_method.method_id, target)

    dot_data = "digraph {\n"
    dot_data += node_def
    dot_data += edge_def
    dot_data += "}\n"

    with open(file_path, "w") as dotfile:
        dotfile.write(dot_data)


def create_summary_feature_vector(instructions, degree, num_total_instr):
    """A function which allows us to create feature vectors from the instructions of a basic block.
    This is a simple summary method which counts groups of.itypes of instruction and returns the resulting vector.
    Args:
        instructions: [Instruction] - The instructions to process
        degree: int - The degree of the basic block the instructions belong to
        num_total_instr: int - The total number of instructions in the entire program
    Returns:
        [int] - A feature vector summarising the types of instructions
    """
    # a really simple feature vector extraction technique - could be improved!
    vector_map = {
           "numeric_const": 0, 
           "transfer": 1,
           "call": 2,
           "arithmetic": 3,
           "compare": 4,
           "move": 5,
           "terminate": 6,
           "data_declaration": 7,
           "num_total_instr": 8,
           "degree": 9,
           "num_instr_in_vertex": 10}
   
    feature_vector = [0]*len(vector_map)

    for instr in instructions:
        if instr.itype == "const":
            feature_vector[vector_map['numeric_const']] += 1

        elif instr.itype in ["fill_arr", "arr_get", "arr_put", "iget", "iput", "sget", "sput", "instance_of"]:
            feature_vector[vector_map['transfer']] += 1

        elif instr.itype in ["invoke"]: # TODO: Should we add conditionals here?
            feature_vector[vector_map['call']] += 1
        
        elif instr.itype in ["neg", "not", "add", "sub", "mul", "div", "rem", "l_and", "l_or", "l_xor", "shift_l", "shift_r", "u_shift_r", "r_sub"]:
            feature_vector[vector_map['arithmetic']] += 1

        elif instr.itype in ["p_switch", "s_switch", "cmp", "if"]: # comparison done in if statements and switches
            feature_vector[vector_map['compare']] += 1
        
        elif instr.itype in ["move"]:
            feature_vector[vector_map['move']] += 1

        elif instr.itype in ["return"]:
            feature_vector[vector_map['terminate']] += 1
        
        elif instr.itype in ["new_inst", "new_arr", "filled_new_arr"]:
            feature_vector[vector_map['data_declaration']] += 1

    feature_vector[vector_map['num_total_instr']] = num_total_instr
    feature_vector[vector_map['degree']] = degree
    feature_vector[vector_map['num_instr_in_vertex']] = len(instructions)
    
    return feature_vector


def output_coo(graph, file_path):
    """Output the graph in COO format
    Args:
        graph: Graph - The graph which holds the program structure
        file_path: str - The path to save the file to
    """
    bb_feature_vectors = []
    
    feature_row = []
    feature_col = []

    adjacency_row = []
    adjacency_col = []
    
    for graph_class in graph.classes:
        for class_methods in graph_class.methods:
            for basic_block in class_methods.basic_blocks:
                # Extract the features of the basic block
                bb_feature_vectors += [create_summary_feature_vector(
                    basic_block.instructions, 
                    len(basic_block.child_block_ids), 
                    graph.instruction_id-1)]
                
                # Set the sparse matrix with the row corresponding to the block
                # and the column 0 (since we're adding a row of the matrix per feature vector)
                feature_row += [basic_block.block_id]
                feature_col += [0]

                # Set the sparse adjacency matrix (column is this block, row is the blocks it's connected to)
                for dest in basic_block.child_block_ids:
                    adjacency_row += [dest]
                    adjacency_col += [basic_block.block_id]
    
    output = "{},{}\n\n".format(len(bb_feature_vectors), len(bb_feature_vectors[0])) # State the number of nodes (basic blocks) and the number of feature vectors
    # Feature matrix data
    output += "{}\n".format(str(bb_feature_vectors))
    output += "{}\n".format(str(feature_row))
    output += "{}\n\n".format(str(feature_col))
    # Adjacency matrix data
    output += "{}\n".format(adjacency_row)
    output += "{}\n".format(adjacency_col)

    with open(file_path, "w") as coo_file:
        coo_file.write(output)
