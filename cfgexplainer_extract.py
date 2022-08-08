"""
Output the generated graph for CFGExplainer
Herath, J.D., Wakodikar, P.P., Yang, P. and Yan, G., 
2022, June. 
CFGExplainer: Explaining Graph Neural Network-Based Malware Classification from Control Flow Graphs. 
In 2022 52nd Annual IEEE/IFIP International Conference on Dependable Systems and Networks (DSN) 
(pp. 172-184). IEEE.
"""
from structures import Graph
import random
from config import logger


def create_cfgexplainer_feature_vector(instructions, degree, num_total_instr):
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
            "numeric_const":        0, 
            "string_const":         1,
            "transfer":             2,
            "call":                 3,
            "arithmetic":           4,
            "compare":              5,
            "move":                 6,
            "terminate":            7,
            "data_declaration":     8,
            "num_total_instr":      9,
            "degree":               10,
            "num_instr_in_vertex":  11
            }
   
    feature_vector = [0]*len(vector_map)

    for instr in instructions:
        if instr.itype == "const":
            feature_vector[vector_map['numeric_const']] += 1
        
        elif instr.itype == "const-string":
            feature_vector[vector_map['string_const']] += 1

        elif instr.itype in ["fill_arr", "arr_get", "arr_put", "iget", "iput", "sget", "sput", "instance_of"]:
            feature_vector[vector_map['transfer']] += 1

        elif instr.itype in ["invoke"]:             
            feature_vector[vector_map['call']] += 1
        
        elif instr.itype in ["neg", "not", "add", "sub", "mul", "div", "rem", "l_and", "l_or", "l_xor", "shift_l", "shift_r", "u_shift_r", "r_sub"]:
            feature_vector[vector_map['arithmetic']] += 1

        elif instr.itype in ["p_switch", "s_switch", "cmp", "if"]:
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


def output_cfgexplainer_coo(graph, file_path):
    """Output the CFG of the graph in COO format (identical to function in `output_graph.py`
    except we include a 2 in the adjacency matrix for inter-class calls)
    Args:
        graph: Graph - The graph which holds the program structure
        file_path: str - The path to save the file to
    """
    bb_feature_vectors = []
    
    feature_row = []
    feature_col = []
    
    adjacency_val = []
    adjacency_row = []
    adjacency_col = []
    
    # We need to be able to discern if a connection to another block is a call
    # so we check the last instruction of the block. If it is an invoke then we
    # set the appropriate value in the adjacency matrix

    for graph_class in graph.classes:
        for class_methods in graph_class.methods:
            for basic_block in class_methods.basic_blocks:
                # Extract the features of the basic block
                bb_feature_vectors += [create_cfgexplainer_feature_vector(
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
                    
                    # Check if the last instruction is invoke
                    if basic_block.instructions[-1].itype == "invoke":
                        adjacency_val += [2]
                    else:
                        adjacency_val += [1]
    
    output = "{},{}\n\n".format(len(bb_feature_vectors), len(bb_feature_vectors[0])) # State the number of nodes (basic blocks) and the number of feature vectors
    # Feature matrix data
    output += "{}\n".format(str(bb_feature_vectors))
    output += "{}\n".format(str(feature_row))
    output += "{}\n\n".format(str(feature_col))
    # Adjacency matrix data
    output += "{}\n".format(adjacency_val)
    output += "{}\n".format(adjacency_row)
    output += "{}\n".format(adjacency_col)

    with open(file_path, "w") as coo_file:
        coo_file.write(output)

