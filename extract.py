"""
Extract the CFG from the apk smali code
"""

import re
import argparse
import glob
from config import logger
from structures import Graph, FileItem
from process_instruction import process_instruction, op_map
from process_manifest import extract_activity_files, extract_permissions 
from output_graph import output_cfg_dotfile, output_cfg_coo, output_fcg_dotfile, output_fcg_coo, restricted_hybrid_dot, restricted_hybrid_coo, interactive_graph

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--dir", help="The path to the directory to process", type=str, required=True)
parser.add_argument("-o", "--out", help="The path of the output file(s)", type=str, default="")
parser.add_argument("-f", "--format", help="Output graph format", choices=['coo', 'dot'])
parser.add_argument("-t", "--type", help="Output graph type", choices=['cfg', 'fcg', 'hybrid'])
parser.add_argument("-e", "--exp_methods", help="Path to the expansion methods file", type=str, default="")
parser.add_argument("-s", "--special", help="Special extraction type using a specific paper implementation (no other arguments apart from -d required)", choices=["cfgexplainer", "malgraph"])

args = parser.parse_args()

# List of all files that make up the runnable application
top_level_dir = args.dir

# Add trailing '/' if necessary
if top_level_dir[-1] != "/":
    top_level_dir += "/"

# Get the name of the output file (sha256)Y
out_file_name = top_level_dir.split("/")[-2]

# Set the output directory
out_dir = ""
if args.out !=  "" and args.out[-1] != "/":
    out_dir += "/"

files_to_process = extract_activity_files(top_level_dir+"/AndroidManifest.xml")
files_to_process = [FileItem(x) for x in files_to_process] # Convert files to FileItem class
if len(files_to_process) == 0:
    logger.critical("Could not extract any files to process from the manifest -- stopping!")
    exit()

permission_list = extract_permissions(top_level_dir+"/AndroidManifest.xml")
if len(permission_list) == 0:
    logger.warning("Could not find any permissions to extract!")

state = Graph(files_to_process)

file_count = 0

for file_item in state.file_list:
    file = file_item.file_name
    file_count += 1
    file = top_level_dir + file # Add path to app directory

    # Attempt to open the next file
    file_success = True
    try:
        with open(file, "r") as smali_file:
            smali_instructions = smali_file.readlines()
    except Exception as e:
        # If we can't open the file as given in the manifest, search the directory for it
        target_file = file.split("/")[-1]
        logger.warning("Failed to open file: {} -- attempting deeper search for {}".format(file, target_file))
        
        for f in glob.glob(top_level_dir+"**/*.smali"):
            if f == target_file:
                logger.warning("Found matching file in search: {}".format(f))
                # Try to open the file again!
                try:
                    with open(f, "r") as smali_file:
                        smali_instructions = smali_file.readlines()
                except Exception as e:
                    logger.warning("Failed to open file: {} -- treating as library function".format(f)) 
                    file_item.make_library = True
                    file_success = False
                    #exit() # TODO: Change this to push file to library instead
                break
        else:
            logger.critical("Failed to find a file which matches {} -- treating as library function".format(target_file))
            file_item.make_library = True
            # exit()
            file_success = False
    
    if not file_success:
        continue


    # Special processing cases (where we have defined start and end directives)
    # annotations
    # fields
    # switches
    # methods
    state.ANNOTATION_FLAG = False
    state.FIELD_FLAG = False
    state.SWITCH_FLAG = False
    state.METHOD_FLAG = False
    
    # Reset the active structures
    state.active_class = None
    state.active_method = None
    state.active_block = None

    # Iterate over the instructions
    for line_num, smali_instr in enumerate(smali_instructions, 1):
        logger.info("Processing instruction: {} : {}".format(line_num, smali_instr.strip().replace("\n", ""))) 
        # Check for a blank line
        if smali_instr == "" or smali_instr == "\n":
            pass # Do nothing!
        else:
            # Strip leading or trailing whitespace
            smali_instr = smali_instr.strip()
            # delete any potential comments after the instruction which could cause processing issues
            smali_instr = smali_instr.split("#")[0]

            # Check for special processing directives (which cause a change in instruction processing)
            if op_map["annotation_start"].match(smali_instr):
                logger.info("Directive encountered - annotation start")
                state.ANNOTATION_FLAG = True
                process_instruction(smali_instr, line_num, state, logger)
            elif op_map["annotation_end"].match(smali_instr): # Need to handle swap to false instructions here, otherwise we'll miss all end instructions
                logger.info("Directive encountered - annotation end")
                process_instruction(smali_instr, line_num, state, logger)
                state.ANNOTATION_FLAG = False
            elif op_map["field_start"].match(smali_instr):
                logger.info("Directive encountered - field start")
                state.FIELD_FLAG = True
                process_instruction(smali_instr, line_num, state, logger)
            elif op_map["field_end"].match(smali_instr):
                logger.info("Directive encountered - field end")
                process_instruction(smali_instr, line_num, state, logger)
                state.FIELD_FLAG = False
            elif op_map["pswitch_start"].match(smali_instr):
                logger.info("Directive encountered - pswitch start")
                state.SWITCH_FLAG = True
                # Need to end field flag (since there are no guarantees it will end with .end field)
                state.FIELD_FLAG = False
                process_instruction(smali_instr, line_num, state, logger)
            elif op_map["pswitch_end"].match(smali_instr):
                logger.info("Directive encountered - pswitch end")
                process_instruction(smali_instr, line_num, state, logger)
                state.SWITCH_FLAG = False
            elif op_map["sswitch_start"].match(smali_instr):
                logger.info("Directive encountered - sswitch start")
                state.SWITCH_FLAG = True
                state.FIELD_FLAG = False
                process_instruction(smali_instr, line_num, state, logger)
            elif op_map["sswitch_end"].match(smali_instr):
                logger.info("Directive encountered - sswitch end")
                process_instruction(smali_instr, line_num, state, logger)
                state.SWITCH_FLAG = False
            elif op_map["method_start"].match(smali_instr):
                logger.info("Directive encountered - method start")
                state.METHOD_FLAG = True
                state.FIELD_FLAG = False
                process_instruction(smali_instr, line_num, state, logger)
            elif op_map["method_end"].match(smali_instr):
                logger.info("Directive encountered - method end")
                process_instruction(smali_instr, line_num, state, logger)
                state.METHOD_FLAG = False
            else:
                process_instruction(smali_instr, line_num, state, logger)

            
    # We have processed the entire file, so offload the blocks, methods and classes to the state
    if state.active_block:
        state.active_method.add_basic_block(state.active_block)
    
    state.active_class.add_method(state.active_method)

    # Resolve any ambiguities in local method calls
    response = state.active_class.resolve_local_invocations()
    if len(response) > 0:
        logger.warning("Local invocation resolution failed!")
        for r in response:
            logger.warning("Class - {} : {}".format(state.active_class, r))

    state.add_class(state.active_class)

# resolve ambiguities in global and library calls
response = state.resolve_global_invocations()
if len(response) > 0:
    logger.warning("Global invocation resolution failed!")
    for r in response:
        logger.warning(r)

response = state.resolve_library_invocations()
if len(response) > 0:
    logger.warning("Library invocation resolution failed!")
    for r in response:
        logger.warning(r)

logger.info("Consumed {} files".format(file_count))
for f in state.file_list:
    logger.info("\t{}".format(f))


if args.format == "dot" and args.type == "cfg":
    output_cfg_dotfile(state, out_dir+out_file_name+".dot")

if args.format == "dot" and args.type == "fcg":
    output_fcg_dotfile(state, out_dir+out_file_name+".dot")

if args.format == "dot" and args.type == "hybrid":
    if args.exp_methods == "":
        logger.critical("Method expansion file not specified -- Please specify a path to a method expansion file using -e")
    else:
        restricted_hybrid_dot(state, out_dir+out_file_name+".dot", args.exp_methods)

if args.format == "coo" and args.type == "hybrid":
    if args.exp_methods == "":
        logger.critical("Method expansion file not specified -- Please specify a path to a method expansion file using -e")
    else:
        restricted_hybrid_coo(state, out_dir+out_file_name+".coo", args.exp_methods)

if args.format == "coo" and args.type == "cfg":
    output_cfg_coo(state, out_dir+out_file_name+".coo")

if args.format == "coo" and args.type == "fcg":
    output_fcg_coo(state, out_dir+out_file_name+".coo")

if args.special == "cfgexplainer":
    from cfgexplainer_extract import output_cfgexplainer_coo
    output_cfgexplainer_coo(state, out_dir+out_file_name+"cfgexplainer.coo")

"""
# MalGraph experiment
import malgraph_extract
malgraph_extract.extract_library_functions(state)
"""

# interactive_graph(state)
