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
            node_def += "{} [shape=box color=\"{}\" label=\"{}\"];\n".format(class_method.method_id, class_color, graph_class.class_name + "::" + class_method.method_name)
            
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

        elif instr.itype in ["invoke"]:             
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


def output_cfg_coo(graph, file_path):
    """Output the CFG of the graph in COO format
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


def output_fcg_coo(graph, filepath):
    """Output the FCG of the graph in COO format
    Args:
        graph: Graph - The graph which has a FCG structure
        file_path: str - The path to save the file to
    """
    m_feature_vectors = []
    
    feature_row = []
    feature_col = []

    adjacency_row = []
    adjacency_col = []

    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            # For each method we get all of the instructions from the basic blocks to generate a feature vector
            method_instrs = []
            for basic_block in class_method.basic_blocks:
               method_instrs += basic_block.instructions

            # Create feature vector from instructions
            m_feature_vectors += [create_summary_feature_vector(
                method_instrs,
                len(class_method.calls_out),
                graph.instruction_id-1)]
            
            # Set feature matrix
            feature_row += [class_method.method_id]
            feature_col += [0]
            
            # Set adjacency matrix (column is method, row details connected methods)
            for dest in class_method.calls_out:
                adjacency_row += [dest]
                adjacency_col += [class_method.method_id]

    output = "{},{}\n\n".format(len(m_feature_vectors), len(m_feature_vectors[0])) # State the number of nodes (basic blocks) and the number of feature vectors
    # Feature matrix data
    output += "{}\n".format(str(m_feature_vectors))
    output += "{}\n".format(str(feature_row))
    output += "{}\n\n".format(str(feature_col))
    # Adjacency matrix data
    output += "{}\n".format(adjacency_row)
    output += "{}\n".format(adjacency_col)

    with open(filepath, "w") as coo_file:
        coo_file.write(output)


def restricted_hybrid_dot(graph, file_path, exp_methods_path):
    """Create a restricted hybrid dot file where only methods which interact with target library functions 
    are expanded into full CFGs (all others remain as single nodes). This creates a hybrid
    between a CFG and a FCG. An empty exp_methods file results in a standard FCG.
    Args:
        graph: Graph - The graph containing the program structure
        file_path: str - The path to save the file to
        exp_methods_path: str - The path to the file containing all the methods to be expanded
    """
    # Read in the target methods to expand
    with open(exp_methods_path, "r") as exp_file:
        exp_targets = exp_file.readlines()
    
    # eliminate all new-lines
    exp_targets = list(map(lambda x: x.strip(), exp_targets))

    # Create a dict of method names as keys and ids as values (so we can pair the id a method calls with the name)
    method_id_map = {}
    id_method_map = {} # JUST FOR DEBUGGING TODO Remove
    block_method_map = {}
    method_block_map = {}
    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            print(graph_class.class_name +"::"+ class_method.method_name)
            print(" {}".format(class_method.param_types))
            # method_id_map stores a list to account for duplciates (overload can occur when different parameters are expected)
            try:
                method_id_map[graph_class.class_name +"::"+ class_method.method_name] += [class_method.method_id]
            except:
                method_id_map[graph_class.class_name +"::"+ class_method.method_name] = [class_method.method_id]
            
            id_method_map[class_method.method_id] = graph_class.class_name +"::"+ class_method.method_name
            method_block_map[class_method.method_id] = class_method.basic_blocks[0].block_id
            # Create a map from block id to the containing method
            for block in class_method.basic_blocks:
                block_method_map[block.block_id] = class_method.method_id

    print(method_id_map)
    exp_method_ids = []
    for target in exp_targets:
        # Check if `*` in target and add all methods of the class if present
        if "*" in target:
            target_class = target.split("::")[0]
            for k in method_id_map.keys():
                k_class = k.split("::")[0]                 
                if target_class == k_class:
                    print("Match found: {} == {}".format(target, k))
                    exp_method_ids += method_id_map[k]
        else:
            for k in method_id_map.keys():
                if target == k:
                    print("Non glob match found: {} == {}".format(target, k))
                    exp_method_ids += method_id_map[k]

    node_def = ""
    edge_def = ""
    
    print("Exp method ids:", exp_method_ids)

    # Find all of the methods to be expanded
    actual_expanded_methods = []
    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            # Check if the method needs to be expanded
            for target in class_method.calls_out:
                if target in exp_method_ids:
                    # If we call out to a salient target expand this method into a CFG
                    actual_expanded_methods += [class_method.method_id]
                    break
    
    # Start by creating a FCG
    for graph_class in graph.classes:
        class_color = "#{}".format("".join(random.choice("0123456789abcedf") for _ in range(6))) # generate a random color per class for the nodes
        for class_method in graph_class.methods:
            # Check if the method needs to be expanded
            for target in class_method.calls_out:
                if target in exp_method_ids:
                    # If we call out to a salient target expand this method into a CFG
                    expand = True
                    break
            else:
                expand = False
            
            if expand:
                # This method is a part of the important graph topology
                print("Expanding method: {}".format(graph_class.class_name + "::" + class_method.method_name))
                
                intra_method_ids = []
                for basic_block in class_method.basic_blocks:
                    # Get internal ids
                    intra_method_ids += [basic_block.block_id]

                for basic_block in class_method.basic_blocks:
                    instructions = ["{}: {}".format(x.line_num, x.instruction.replace("$", "•").replace('"', "'")) for x in basic_block.instructions]
                    instructions = "\l".join(instructions) + "\l" # \l for left alignment in the dotfile
                    node_def += "i{} [shape=box color=\"{}\" label=\"{}\"];\n".format(basic_block.block_id, class_color, instructions)

                    for target in basic_block.child_block_ids:
                        # All targets should be first basic block of method, so no changes need to be made to target
                        # Check if target is another method - if it is, don't use the `i` prefix for internal nodes (to avoid method id, block id clashes)
                        if target in intra_method_ids:
                            edge_def += "i{} -> i{};\n".format(basic_block.block_id, target)
                        elif block_method_map[target] in actual_expanded_methods:
                            # Check if the target has been expanded and link to start block if it has (rather than method)
                            print("External connection to expanded method! i{} -> {} ~> {} ~> {}".format(basic_block.block_id, target, block_method_map[target], id_method_map[block_method_map[target]]))
                            edge_def += "i{} -> i{};\n".format(basic_block.block_id, target) # I don't think errors will happen here... TODO Check! 
                        else:
                            # target will be basic block id of the leading block of the method, so need to convert it to method id
                            print("External connection! i{} -> {} ~> {} ~> {}".format(basic_block.block_id, target, block_method_map[target], id_method_map[block_method_map[target]]))
                            edge_def += "i{} -> {};\n".format(basic_block.block_id, block_method_map[target])
            else:
                # Continue as a normal FCG
                node_def += "{} [shape=box color=\"{}\" label=\"{}\"];\n".format(class_method.method_id, class_color, graph_class.class_name + "::" + class_method.method_name)
                for target in class_method.calls_out:
                    # check if target has been expanded
                    if target in actual_expanded_methods:
                        edge_def += "{} -> i{};\n".format(class_method.method_id, method_block_map[target])
                        print("Node has been expanded!")
                    else:
                        edge_def += "{} -> {};\n".format(class_method.method_id, target)

    dot_data = "digraph {\n"
    dot_data += node_def
    dot_data += edge_def
    dot_data += "}\n"

    with open(file_path, "w") as dotfile:
        dotfile.write(dot_data)

def restricted_hybrid_coo(graph, file_path, exp_methods_path):
    """Create a restricted hybrid coo file where only methods which interact with target functions 
    are expanded into full CFGs (all others remain as single nodes). This creates a hybrid
    between a CFG and a FCG. An empty exp_methods file results in a standard FCG.
    Args:
        graph: Graph - The graph containing the program structure
        file_path: str - The path to save the file to
        exp_methods_path: str - The path to the file containing all the methods that cause expansion
    """
    # Need to do some index manipulation for the COO generation (to avoid larger matrices than necessary)
    global_id_map = {} # Translate from a local ID to a global one
    global_idx = 0
    vertices = []
    edges = {} # dictionary with key vertex and values connected vertices
    
    # Read in the target methods which cause expansion
    with open(exp_methods_path, "r") as exp_file:
        exp_targets = exp_file.readlines()
    
    # eliminate all new-lines
    exp_targets = list(map(lambda x: x.strip(), exp_targets))

    # Create a dict of method names as keys and ids as values (so we can pair the id a method calls with the name)
    method_id_map = {}
    id_method_map = {} # JUST FOR DEBUGGING TODO Remove
    block_method_map = {}
    method_block_map = {}
    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            global_id_map["m"+str(class_method.method_id)] = global_idx 
            global_idx += 1
            print(graph_class.class_name +"::"+ class_method.method_name)
            print(" {}".format(class_method.param_types))
            # method_id_map stores a list to account for duplciates (overload can occur when different parameters are expected)
            try:
                method_id_map[graph_class.class_name +"::"+ class_method.method_name] += [class_method.method_id]
            except:
                method_id_map[graph_class.class_name +"::"+ class_method.method_name] = [class_method.method_id]
            
            id_method_map[class_method.method_id] = graph_class.class_name +"::"+ class_method.method_name
            method_block_map[class_method.method_id] = class_method.basic_blocks[0].block_id
            # Create a map from block id to the containing method
            for block in class_method.basic_blocks:
                global_id_map["b"+str(block.block_id)] = global_idx
                global_idx += 1
                block_method_map[block.block_id] = class_method.method_id

    print(method_id_map)
    # Get all the method ids that cause expansion
    exp_method_ids = []
    for target in exp_targets:
        # Check if `*` in target and add all methods of the class if present
        if "*" in target:
            target_class = target.split("::")[0]
            for k in method_id_map.keys():
                k_class = k.split("::")[0]                 
                if target_class == k_class:
                    print("Match found: {} == {}".format(target, k))
                    exp_method_ids += method_id_map[k]
        else:
            for k in method_id_map.keys():
                if target == k:
                    print("Non glob match found: {} == {}".format(target, k))
                    exp_method_ids += method_id_map[k]

    print("Exp method ids:", exp_method_ids)

    # Find all of the methods to be expanded
    actual_expanded_methods = []
    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            # Check if the method needs to be expanded
            for target in class_method.calls_out:
                if target in exp_method_ids:
                    # If we call out to a salient target expand this method into a CFG
                    actual_expanded_methods += [class_method.method_id]
                    break
    
    # Start by creating a FCG
    for graph_class in graph.classes:
        for class_method in graph_class.methods:
            # Check if the method needs to be expanded
            for target in class_method.calls_out:
                if target in exp_method_ids:
                    # If we call out to a salient target expand this method into a CFG
                    expand = True
                    break
            else:
                expand = False
            
            if expand:
                # This method is a part of the important graph topology
                print("Expanding method: {}".format(graph_class.class_name + "::" + class_method.method_name))
                
                # Get intra-method ids so we can keep internal method calls consistent (we don't accidentally make a call to an external method)
                intra_method_ids = []
                for basic_block in class_method.basic_blocks:
                    # Get internal ids
                    intra_method_ids += [basic_block.block_id]

                for basic_block in class_method.basic_blocks:
                    # Check if basic block id is in the global map
                    b_id = "b"+str(basic_block.block_id)
                    try:
                        src_id = global_id_map[b_id]
                        vertices += [src_id]
                    except:
                        print("ID search failed! 1")

                    for target in basic_block.child_block_ids:
                        # All targets should be first basic block of method, so no changes need to be made to target
                        # Check if target is another method - if it is, don't use the `i` prefix for internal nodes (to avoid method id, block id clashes)
                        if target in intra_method_ids:
                            t_id = "b"+str(target)
                            try:
                                target_id = global_id_map[t_id]
                            except:
                                print("Fail 2") 
                            # Add as an edge
                            try:
                                edges[src_id] += [target_id]
                            except:
                                edges[src_id] = [target_id]

                        elif block_method_map[target] in actual_expanded_methods:
                            # Check if the target has been expanded and link to start block if it has (rather than method)
                            print("External connection to expanded method! i{} -> {} ~> {} ~> {}".format(basic_block.block_id, target, block_method_map[target], id_method_map[block_method_map[target]]))
                            t_id = "b"+str(target)
                            try:
                                target_id = global_id_map[t_id]
                            except:
                                print("Fail 3") 
                            
                            try:
                                edges[src_id] += [target_id]
                            except:
                                edges[src_id] = [target_id]

                        else:
                            # target will be basic block id of the leading block of the method, so need to convert it to method id
                            print("External connection! i{} -> {} ~> {} ~> {}".format(basic_block.block_id, target, block_method_map[target], id_method_map[block_method_map[target]]))
                            t_id = "b"+str(target)
                            try:
                                target_id = global_id_map[t_id]
                            except:
                                print("Fail 4")

                            try:
                                edges[src_id] += [target_id]
                            except:
                                edges[src_id] = [target_id]

            else:
                # Continue as a normal FCG
                m_id = "b"+str(method_block_map[class_method.method_id])
                try:
                    src_id = global_id_map[m_id]
                    vertices += [src_id]
                except:
                    print("Fail 5")

                for target in class_method.calls_out:
                    # check if target has been expanded
                    if target in actual_expanded_methods:
                        print("Node has been expanded!")
                        t_id = "b"+str(method_block_map[target])
                        try:
                            target_id = global_id_map[t_id]
                        except:
                            print("Fail 6")

                        try:
                            edges[src_id] += [target_id]
                        except:
                            edges[src_id] = [target_id]

                    else:
                        t_id = "b"+str(method_block_map[target])
                        try:
                            target_id = global_id_map[t_id]
                        except:
                            print("Fail 7")

                        try:
                            edges[src_id] += [target_id]
                        except:
                            edges[src_id] = [target_id]

    # Create the COO graph
    hybrid_feature_vectors = [] # Maybe better to add whenever we define a new vertex??
    feature_row = []
    feature_col = []

    adjacency_row = []
    adjacency_col = []

    for vertex in edges.keys():
        # Add the targets if they exist
        try:
            for target in edges[vertex]:
                adjacency_row += [target]
                adjacency_col += [vertex]
        except:
            pass

    output = "{},{}\n\n".format(0, 0) # TODO: Should be len(hybrid_feature_vectors), len(hybrid_feature_vectors[0])
    # Feature matrix data
    output += "{}\n".format(str(hybrid_feature_vectors))
    output += "{}\n".format(str(feature_row))
    output += "{}\n\n".format(str(feature_col))
    # Adjacency matrix data
    output += "{}\n".format(adjacency_row)
    output += "{}\n".format(adjacency_col)

    with open(file_path, "w") as coo_file:
        coo_file.write(output)


def interactive_graph(graph):
    with open("graph_draw_template.js", "r") as gt:
        graph_data = gt.read()
    
    for graph_class in graph.classes:
        for class_methods in graph_class.methods:
            for basic_block in class_methods.basic_blocks:
                instructions = ["{}: {}".format(x.line_num, x.instruction.replace("$", "•").replace('"', "'")) for x in basic_block.instructions]
                instructions = "\n".join(instructions)
                graph_data += "blocks.set({}, new Block({}, {}, \"{}\", [], {}, {}));\n".format(
                        basic_block.block_id, 
                        basic_block.block_id,
                        repr(instructions),
                        "Extra text",
                        random.randint(0, 10000),
                        random.randint(0, 10000))

                graph_data += "edges.set({}, {});\n".format(basic_block.block_id, str(basic_block.child_block_ids))
    
    graph_data += "}"

    with open("ig_test.js", "w") as gfile:
        gfile.write(graph_data)
