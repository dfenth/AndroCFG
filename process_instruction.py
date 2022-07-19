"""
Process the smali instructions using the provided state
"""
import re
from structures import *

# Precompiled regex for all of the instructions
op_map = {
        # Dalvik Bytecode
        "nop":              re.compile("^nop"),
        "move":             re.compile("^move"),
        "return":           re.compile("^return"), # BB terminator
        "const":            re.compile("^const"),
        "monitor":          re.compile("^monitor"),        
        "cast_check":       re.compile("^check\-cast"),
        "instance_of":      re.compile("^instance\-of"),
        "array_len":        re.compile("^array\-length"),
        "new_inst":         re.compile("^new\-instance"),
        "new_arr":          re.compile("^new\-array"),
        "filled_new_arr":   re.compile("^filled\-new\-array"),
        "fill_arr":         re.compile("^fill\-array\-data"),
        "throw":            re.compile("^throw"),
        "goto":             re.compile("^goto"), # BB terminator
        "p_switch":         re.compile("^packed\-switch"), # BB terminator
        "s_switch":         re.compile("^sparse\-switch"), # BB terminator
        "cmp":              re.compile("^cmp"), 
        "if":               re.compile("^if\-"), # BB terminator
        "arr_get":          re.compile("^aget"),
        "arr_put":          re.compile("^aput"),
        "iget":             re.compile("^iget"),
        "iput":             re.compile("^iput"),
        "sget":             re.compile("^sget"),
        "sput":             re.compile("^sput"),
        "invoke":           re.compile("^invoke"), # BB terminator
        "neg":              re.compile("^neg"),
        "not":              re.compile("^not"),
        "int_conv":         re.compile("^int\-to"),
        "long_conv":        re.compile("^long\-to"),
        "float_conv":       re.compile("^float\-to"),
        "double_conv":      re.compile("^double\-to"),
        "add":              re.compile("^add\-"),
        "sub":              re.compile("^sub\-"),
        "mul":              re.compile("^mul\-"),
        "div":              re.compile("^div\-"),
        "rem":              re.compile("^rem\-"),
        "l_and":            re.compile("^and\-"),
        "l_or":             re.compile("^or\-"),
        "l_xor":            re.compile("^xor\-"),
        "shift_l":          re.compile("^shl\-"),
        "shift_r":          re.compile("^shr\-"),
        "u_shift_r":        re.compile("^ushr\-"),
        "r_sub":            re.compile("^rsub\-"),

        # Directives
        "class":            re.compile("^\.class"),
        "super":            re.compile("^\.super"),
        "source":           re.compile("^\.source"),
        "method_start":     re.compile("^\.method"), # BB terminator
        "method_end":       re.compile("^\.end method"), # BB terminator
        "field_start":      re.compile("^\.field"),
        "field_end":        re.compile("^\.end field"),
        "label":            re.compile("^\:"), # BB leader
        "comment":          re.compile("^\#"),
        "line":             re.compile("^\.line"),
        "local_var":        re.compile("^\.local"),
        "param":            re.compile("^\.param"),
        "annotation_start": re.compile("^\.annotation"),
        "annotation_end":   re.compile("^\.end annotation"),

        # Undocumented directives for packed-switch and sparse-switch
        "pswitch_start":    re.compile("^\.packed\-switch"),
        "pswitch_end":      re.compile("^\.end packed\-switch"),
        "sswitch_start":    re.compile("^\.sparse\-switch"),
        "sswitch_end":      re.compile("^\.end sparse\-switch"),
}

def terminate_and_start_block(state, instruction):
    """Terminate a block if a termination flag has been set and start the next one!
    Args:
        state: Graph - The state to check a terminating block of
        instruction: Instruction - The next instruction
    """
    # Handle the block
    logger.debug("Previous instruction called for block termination -- terminating block and creating a new one")
    # Stop the current block, push it to the method and start a new one!
    # check if a block exists first (since the first method in a class has no active block to push to)
    parent_id = None
    if state.active_block != None:
        state.active_block.add_child_block_id(state.block_id)
        parent_id = state.active_block.block_id
        state.active_method.add_basic_block(state.active_block)
        logger.debug("Pushed block {} to method {}".format(state.active_block.block_id, state.active_method.method_name))
        state.active_block = None
    
    state.block_term = False
    
    state.active_block = BasicBlock(state.block_id, instruction)
    if parent_id != None:
        state.active_block.add_parent_block_id(parent_id)
    state.block_id += 1


def process_instruction(instr, line_num, state, logger):
    """Process the provided instruction in the state context
    Args:
        instr: str - The instruction to process
        line_num: int - The line number
        state: Graph (mutable) - The global state
        logger: - The active logger (maybe want to have separate logger for this?)
    """
    # Check flags for how to process the instruction
    if state.ANNOTATION_FLAG:
        logger.debug("ANNOTATION_FLAG active")
        # Check if the annoation is a part of a method or field
        if state.METHOD_FLAG:
            logger.debug("METHOD_FLAG active (with ANNOTATION)")
            state.active_method.add_annotation(instr)
        elif state.FIELD_FLAG:
            logger.debug("FIELD_FLAG active (with ANNOTATION)")
            state.active_class.add_field(instr)
        else:
            logger.debug("class level annotation active")
            state.active_class.add_annotation(instr)

    elif state.FIELD_FLAG:
        logger.debug("FIELD_FLAG active")
        state.active_class.add_field(instr)
    
    elif state.SWITCH_FLAG:
        logger.debug("SWITCH_FLAG active")
        # we're in a switch statement so take all of the labels and place them in an expansion dictionary e.g. `{":pswitch_data_0" : [":pswitch_2", ":pswitch_1", ":pswitch_0"]}`
        # where each reference to `:pswitch_data_0` is expanded to the three 'aliases' resolved at the end of the method (just like normal labels)
       
        # if this is the directive line get the previous label
        if op_map["pswitch_start"].match(instr) or op_map["sswitch_start"].match(instr):
            state.active_method.previous_label = state.active_block.instructions[-1].instruction
            state.active_method.label_aliases[state.active_method.previous_label] = []
       
            state.active_block = None # Reset the active block since this isn't a real control flow!
        
        elif op_map["label"].match(instr):
            # Add the instruction as an alias
            state.active_method.label_aliases[state.active_method.previous_label] += [instr]
        
        elif op_map["pswitch_end"].match(instr) or op_map["sswitch_end"].match(instr):
            # Ended the switch instruction so do nothing!
            pass

        else:
            logger.warning("Encountered unexpected instruction in switch statement: {}".format(instr))

    elif state.METHOD_FLAG:
        logger.debug("METHOD_FLAG active")
        # Process instructions within the context of a method
        
        # Handle the instruction
        if op_map["method_start"].match(instr):
            # On matched method_start we want to end the old method and start a new one
            logger.debug("Method matched - {}".format(instr))
            if state.active_method != None: # The first method of a file will have no previous method to push, so we need to check for this case    
                # Push active block and method to the class
                state.active_method.add_basic_block(state.active_block)
                state.active_class.add_method(state.active_method)
                logger.debug("Pushed previous method {} to class".format(state.active_method.method_name))

            # Start new block and method
            logger.debug("Creating new method")
            state.active_method = Method(state.method_id, instr)
            state.method_id += 1

            instruction = Instruction(
                    instr, 
                    "method_start", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.block_id)
            
            state.instruction_id += 1
            state.block_id += 1
            
            # start a new block
            block = BasicBlock(state.block_id, instruction)
            state.block_id += 1
            state.active_block = block

            # start a new method
            state.active_method = Method(state.method_id, instr)
            state.method_id += 1

            if state.block_term:
                state.block_term = False
                
        elif op_map["method_end"].match(instr):
            # Set the block termination flag to end the current method
            
            instruction = Instruction(
                    instr, 
                    "method_end", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)
            
            # End of a method so terminate the block
            state.block_term = True
            
            # label resolution
            logger.debug("Attempting to resolve labels for {}".format(state.active_method.method_name))
            failures = state.active_method.resolve_labels()
            if len(failures) > 0:
                for f in failures:
                    logger.warn("{} - Method: {}".format(f, state.active_method.method_name))

        elif op_map["label"].match(instr):
            # label is a leader (since it is a target of a goto), so end current block and add label as the start of a new one
            state.active_block.add_child_block_id(state.block_id)
            state.active_method.add_basic_block(state.active_block)
            parent_id = state.active_block.block_id

            # Start new block
            instruction = Instruction(
                    instr, 
                    "label", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)
            
            state.instruction_id += 1
            # create the new label led basic block
            state.active_block = BasicBlock(state.block_id, instruction)
            state.active_block.add_parent_block_id(parent_id)
            state.block_id += 1
 
            state.instruction_id += 1

        elif op_map["return"].match(instr):
            instruction = Instruction(
                    instr, 
                    "return", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)
            
            # set the block termination flag!
            state.block_term = True
            # TODO: Could do more interesting things with return types in the future...

        elif op_map["goto"].match(instr):
            # an unconditional statement which ends the block (this block will be parent of both the call location and the next instructions in the file)
            # this will reference a label within the same method, so add the call to a list to process at the end of the method
            
            
            instruction = Instruction(
                    instr, 
                    "goto", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)
            
            state.block_term = True
            
            # add the label destination to a list to be resolved at the end of the **method**
            state.active_method.add_label_call(instr, state.active_block.block_id)
        
        elif op_map["if"].match(instr):
            # conditional statement which ends the block (this block will be the parent of both the call location and the next instructions in the file)
            # this references a label within the same method, so add to a list to process at the end of the method
            # the code is the same as `goto` but kept separate in case we want to add variable tracking (tainting) later    
            instruction = Instruction(
                    instr, 
                    "if", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)
            
            # add the label destination to a list to be resolved at the end of the **method**
            state.active_method.add_label_call(instr, state.active_block.block_id)
            state.block_term = True
        
        elif op_map["invoke"].match(instr):
            # invocation of another method (can be within the same class or from a completely different one)
            # we need to differentiate between library calls and within app calls to make sure our CFGs capture relevant information
            # if the instruction contains `Lcom` along with the class name, it is local, if `Lcom` is present but no class name, it is from the app, neither, it is a library
            logger.debug("Encountered invocation!")
            
            instruction = Instruction(
                    instr, 
                    "invoke", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)

            state.block_term = True
            # add to the list of invocations to sort later!
            state.active_class.add_invocation(instr, state.active_method.method_id, state.active_block.block_id, state.file_list)
        
        elif op_map["line"].match(instr):
            # do nothing! .line is a disassembly artifact we don't need!
            pass
        else:
            # Catch for all other instructions
            logger.debug("Instruction fallthrough: {}".format(instr))
            instruction = Instruction(
                    instr, 
                    "other", 
                    state.instruction_id, 
                    line_num, 
                    state.active_method.method_id, 
                    state.active_class.class_id, 
                    state.active_block.block_id)

            state.instruction_id += 1
            
            if state.block_term:
                terminate_and_start_block(state, instruction)
            else:
                state.active_block.add_instruction(instruction)


    else:
        # Process instructions outside of a context (this should happen at the start of a new class)
        if op_map["class"].match(instr):
            # push active class/method/block to the graph <- done in level above
            state.active_class = SmaliClass(state.class_id, instr)
            state.class_id += 1
        elif op_map["super"].match(instr):
            state.active_class.add_super(instr)
        elif op_map["source"].match(instr):
            state.active_class.add_source(instr)
        elif op_map["comment"].match(instr):
            pass # Comments are ignored
        else:
            if instr.replace("\n", "") != "":
                logger.warning("Unhandled instruction outside of context: {} :: {}: {}".format(state.active_class.class_name, line_num, instr))
