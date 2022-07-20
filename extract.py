"""
Extract the CFG from the apk smali code
Details on operations can be found here:
https://source.android.com/devices/tech/dalvik/dalvik-bytecode.html
"""

import re
import logging
import config
from structures import Graph 
from process_instruction import process_instruction, op_map
from process_manifest import extract_activity_files, extract_permissions 
from output_graph import output_cfg_dotfile, output_coo, output_fcg_dotfile  

log_to_file = False

if log_to_file:
    handler = logging.FileHandler("file.log")
else:
    handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter("%(name)s:%(levelname)s:: %(message)s"))
logger = logging.getLogger("CFGGen")
logger.setLevel(config.LOG_LEVEL)
logger.addHandler(handler)

# List of all files that make up the runnable application
top_level_dir = "../LoginApp/" # TODO: Get as input from command line

files_to_process = extract_activity_files(top_level_dir+"/AndroidManifest.xml")
if len(files_to_process) == 0:
    logger.critical("Could not extract any files to process from the manifest -- stopping!")
    exit()

permission_list = extract_permissions(top_level_dir+"/AndroidManifest.xml")
if len(permission_list) == 0:
    logger.warning("Could not find any permissions to extract!")

state = Graph(files_to_process)

file_count = 0

for file in state.file_list:
    file_count += 1
    file = top_level_dir + file # Add path to app directory

    # Attempt to open the next file
    try:
        with open(file, "r") as smali_file:
            smali_instructions = smali_file.readlines()
    except Exception as e:
        logger.critical("Failed to open file: {} -- stopping execution!".format(file))
        exit()

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
            elif op_map["annotation_end"].match(smali_instr): #TODO: Need to handle swap to false instructions here, otherwise we'll miss all end instructions
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

output_cfg_dotfile(state, "testfile.dot")
output_fcg_dotfile(state, "testfile_fcg.dot")
output_coo(state, "testfile.coo")
