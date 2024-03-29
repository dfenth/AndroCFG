"""Convert COO files to dotfiles to check the graph compression
"""
import sys
import re
import ast

def coo_to_dot(src_path, res_path):
    """Convert COO sparse matrix format graphs to dotfile for visualisation
    Args:
        src_path: str - The path to the source COO file
        res_path: str - The path for dotfile saving
    """
    with open(src_path, 'r') as coo_file:
        coo_lines = coo_file.readlines()

    src_line = coo_lines[7].strip()
    target_line = coo_lines[6].strip()
    
    instr_flag = False
    try:
        instr_data = coo_lines[9].strip()
        instr_data = ast.literal_eval(instr_data) # Convert the string of dict to a dict
        instr_flag = True
        print("Verbose instruction data found!")
    except:
        print("No verbose instruction data found")

    src_line = src_line.replace("[", "").replace("]", "").replace(" ", "")
    target_line = target_line.replace("[", "").replace("]", "").replace(" ", "")
    
    src_vertices = src_line.split(",")
    target_vertices = target_line.split(",")
    
    dot_text = "digraph {\n"
    
    if instr_flag:
        for k in instr_data:
            # k is the node id, instr_data[k] is the node instructions
            instructions = ["{}".format(x.replace("$", "•").replace('"', "'")) for x in instr_data[k]]
            instructions = "\l".join(instructions) + "\l" # \l for left alignment in the dotfile
            dot_text += "{} [shape=box label=\"{}\"];\n".format(k, instructions)
    
    for s,t in zip(src_vertices, target_vertices):
        dot_text += "{} -> {};\n".format(s, t)

    dot_text += "}"

    with open(res_path, "w") as dot_file:
        dot_file.write(dot_text)

def count_edges(path):
    """Count the edges in a dotfile
    Args:
        path: str - Path to the dotfile
    """
    pattern = re.compile(r'(\"\S+\"|\w+)\s*\-\>\s*(\"\S+\"|\w+)\;')
    
    with open(path, 'r') as dotfile:
        dotlines = dotfile.readlines()
    
    count = 0
    for line in dotlines:
        if pattern.match(line):
            count += 1
    
    print("{} edges present".format(count))

if __name__ == "__main__":
    coo_to_dot(sys.argv[1], sys.argv[2])
    # count_edges(sys.argv[1])
