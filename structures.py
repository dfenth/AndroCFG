"""
Holds all of the program structures we need to represent smali intermediate code as a program graph
"""
import re
import logging
import config

log_to_file = False

if log_to_file:
    handler = logging.FileHandler("file.log")
else:
    handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter("%(name)s:%(levelname)s:: %(message)s"))
logger = logging.getLogger("Structures")
logger.setLevel(config.LOG_LEVEL)
logger.addHandler(handler)


invoke_params_regex = re.compile(r"\{(.*?)\}")
invoke_class_regex = re.compile(r"\sL\w+(\/\w+)+(\S)*;->") # Remember to strip whitespace and get rid of `;->`

class Instruction():
    """An instruction class for storing all of the attributes
    of an instruction from the smali intermediate code"""

    def __init__(self, instr, itype, instr_id, line_num, method_id, class_id, block_id):
        """Initialise the Instruction object
        Args:
            instr: str - The instruction text (operation and parameters)
            itype: str - The type of the instruction (same types as regex list)
            instr_id: int - The unique instruction id
            line_num: int - The line number within the class file
            method_id: int - The method the instruction belongs to
            class_id: int - The class the instruction belongs to
            block_id: int - The block the instruction belongs to
        """
        self.instruction = instr
        self.itype       = itype
        self.instr_id    = instr_id
        self.line_num    = line_num
        self.method_id   = method_id
        self.class_id    = class_id
        self.block_id    = block_id


class BasicBlock():
    """A basic block class which stores information about instructions that
    create it"""

    def __init__(self, block_id, leader):
        """Initialise the BasicBlock object
        Args:
            block_id: int - The unique block id
            leader: Instruction - The leading instruction which starts the new block
        """
        self.block_id         = block_id
        self.instructions     = [leader]
        self.parent_block_ids = []
        self.child_block_ids  = []
        self.unresolved_calls = [] # A list of calls to be resolved later (these should always be outgoing calls)
    
    def add_instruction(self, instruction):
        """Add an instruction to the basic block object
        Args:
            instruction: Instruction - The instruction to add
        """
        self.instructions += [instruction]
        # NOTE: Not processing instruction here since we have the instruction which implies we already know it's information
        # Instruction processing done outside of this method because the instruction may have some global state change to make (e.g. trigger annotation)
    
    def add_parent_block_id(self, parent_id):
        """Add a parent block id to this basic block to create the program graph
        Args:
            parent_id: int - The unique id of the parent block
        """
        self.parent_block_ids += [parent_id]

    def add_child_block_id(self, child_id):
        """Add a child block id to this basic block to create the program graph
        Args:
            child_id: int - The unique id of the child block
        """
        self.child_block_ids += [child_id]
    
    def add_unresolved(self, instruction):
        """Add an unresolved call to the basic block (an outgoing call which has not yet been expanded into a basic block)
        Args:
            instruction: Instruction - The Instruction of the unresolvable call
        """
        # These must be resolved after all files have been processed!
        self.unresolved_calls += [instruction.line_num] # Just store the line number (avoid object ambiguity)
        

class Method():
    """A method class for storing method information. 
    Required because function calls reference a method"""

    def __init__(self, method_id, method_instr):
        """Initialise the Method object
        Args:
            method_id: int - The unique method id
            method_inst: str - The method instruction
        """
        method_name, param_types, return_type = self.process_method_directive(method_instr)

        self.method_id        = method_id
        self.method_name      = method_name
        self.return_type      = return_type
        self.param_types      = param_types
        self.basic_blocks     = []
        self.calls_out        = [] # The methods this method calls
        self.calls_in         = [] # The methods that call this one
        self.annotation       = [] # Methods can also have annotations...
        self.label_calls      = [] # The label calls which are local to the method tuple: (label, caller_id)
        
        self.previous_label = None # Storage for the previous label if we reach a switch
        self.label_aliases = {} # A dictionary to store label aliases for switch statements
    
    @staticmethod
    def process_method_directive(instr):
        """Process the method directive in smali intermediate code
        Args:
            instr: str - The instruction which defines the start of the method
        Returns:
            A tuple (method_name: str, method_param_types: [str], return_type: str)
        """
        directive_fragments = instr.split(" ")
        # index 1 is for public/private
        # index 2 is for final/constructor
        # last index will be method name etc.
        name_param_type_info = directive_fragments[-1]
        npt_fragments = re.split("\(|\)", name_param_type_info) # name param type fragments
        method_name = npt_fragments[0]
        param_types = npt_fragments[1]
        return_type = npt_fragments[2]
        
        # Split param types if more than one exists
        param_types = param_types.split(";")

        return method_name, param_types, return_type

    def add_basic_block(self, basic_block):
        """Add a basic block to the list of basic blocks that make up this method
        Args:
            basic_block: BasicBlock - The basic block object to add to the list
        """
        self.basic_blocks += [basic_block]

    def add_call_out(self, target_method_id):
        """Add a call from this method to another (useful if we want to ignore all Basic Blocks and focus on a FCG)
        Args:
            target_method_id: int - The unique id of the method that is targeted by the call
        """
        self.calls_out += [target_method_id]

    def add_call_in(self, source_method_id):
        """Add a connection between a calling method and this one
        Args:
            source_method_id: int - Add the id of the method that calls this one
        """
        self.calls_in += [source_method_id]
    
    def add_annotation(self, annotation_line):
        """Add an annotation to the method (still not entirely sure what this means...)
        Args:
            annotation_line: str - The annotation line
        """
        self.annotation += [annotation_line]

    def add_label_call(self, instr, b_id):
        """Add a label call to the method (which should be resolved internally at the end of the method)
        Args:
            instr: str - The label instruction which has the form goto :label_name
            b_id: int - The id of the block that makes the call
        """
        label_name = instr.split(" ")[-1]
        self.label_calls += [(label_name, b_id)]

    def resolve_labels(self) -> [str]:
        """Should be called at the end of a method (at the `.method end` instruction).
        This resolves all labels in the method adding connections between the participating basic blocks
        Returns:
            A string of failed resolutions (check length to see if we have any failures)
        """
        report = []
        logger.debug("Label calls to resolve pre alias check: {}".format(self.label_calls))
        
        # check for label aliases
        expanded_calls = []
        for label, caller in self.label_calls:
            try:
                aliases = self.label_aliases[label]
                for a in aliases:
                    expanded_calls += [(a, caller)]

            except:
                expanded_calls += [(label, caller)]

        logger.debug("Label calls to resolve post alias check: {}".format(expanded_calls))
        
        for label, caller in expanded_calls:
            logger.debug("Attempting to resolve label: {} -> {}".format(caller, label))
            # Add the id of the basic block that has label as the leader to the caller child block list
            # Could improve performance by adding basic blocks into a dictionary indexed by block id, but... effort
            for target_bb in self.basic_blocks:
                success = False
                logger.debug("target_bb instruction: {}".format(target_bb.instructions[0].instruction))
                if label == target_bb.instructions[0].instruction:
                    # Got the basic block for the label, search for the caller
                    logger.debug("Got basic block of label!")
                    target_basic_block = target_bb
                    success = True
                    break
            else:
                logger.warning("Failed to get the basic block of the label - {}".format(label))
                
            if success:
                # We have the target basic block, so continue
                for source_bb in self.basic_blocks:
                    if source_bb.block_id == caller:
                        logger.debug("Got source block of caller!")
                        # Got the source basic block! Connect the two
                        source_bb.add_child_block_id(target_basic_block.block_id)
                        target_basic_block.add_parent_block_id(source_bb.block_id)
                        break
                else:
                    logger.warning("Failed to get source block of the caller!")
        return report
    

class SmaliClass():
    """A class for storing information about the Smali class we are processing"""

    def __init__(self, class_id, class_header):
        """Initialise the SmaliClass object
        Args:
            class_id: int - The unique class id
            class_header: str - The class header instruction
        """
        self.class_name, self.class_path = self.process_class_header(class_header)
        self.class_id           = class_id
        self.super_class        = "" # The super class
        self.source             = None # The katex source (if one exists)
        self.annotations        = [] # The annotations section of the class file (contains field, method and parameter data) # TODO: Think about how we can process!
        self.fields             = [] # The fields defined at the start of the class # TODO: Think about how best to process these
        self.methods            = [] # The methods that make up the class
        self.invocations_local  = [] # The local invocations made by methods in the class [(src_method_id, src_block_id, target_method_name)]
        self.invocations_global = [] # The global invocations made by methods in the class [(src_method_id, src_block_id, target_class_name, target_method_name)]
        self.invocations_lib    = [] # The library invocations made by methods in the class [(src_method_id, src_block_id, target_class_name, target_method_name)]

    @staticmethod
    def process_class_header(class_header):
        """Process the class header instruction extracting class name and class path
        Args:
            class_header: str - The class header instruction
        Returns:
            A tuple containing the class name and path to the class (class_name, class_path)
        """
        class_header_fragments = class_header.split(" ")
        class_name_and_path = class_header_fragments[-1]
        class_path_fragments = class_name_and_path.split("/")
        class_name = class_path_fragments[-1].replace(";", "")
        class_path  = "/".join(class_path_fragments[:len(class_path_fragments)-1])
        
        return class_name, class_path
    
    def add_annotation(self, line):
        """Add a line to the annotation field
        Args:
            line: str - The annotation line (nothing more advanced than string because there is no clear structure)
        """
        self.annotations += line

    def add_field(self, line):
        """Add a line to field
        Args:
            line: str - The field line of text (again, nothing sophisticated since fields are a mystery)
        """
        self.fields += line
    
    def add_method(self, method):
        """Add a method that belongs to the class
        Args:
            method: Method - The method to add
        """
        self.methods += [method]

    def add_super(self, instr):
        """Add the super class from the instruction provided
        Args:
            instr: str - The instruction with the super class
        """
        instr_fragments = instr.split(" ")
        self.super_class = instr_fragments[-1].replace(";", "")
    
    def add_source(self, instr):
        """Add the source class from the instruction
        Args:
            instr: str - The source instruction
        """
        instr_fragments = instr.split(" ")
        self.source = instr_fragments[-1].replace('"', "")
    
    def add_invocation(self, instr, method_id, block_id, state_file_list):
        """Add the invocation as either a local, global or library 
        Args:
            instr: str - The invocation instruction to process
            method_id: int - The id of the method the invocation is made from
            block_id: int - The id of the block the invocation is made from
            state_file_list: [str] - A list of files to be processed (so we can check for duplicate calls)
        """
        # invoke_params_regex exists if we want to do any processing of the arguments
        # extract the target class and method so we can see what kind of call is being made (local, global, library)
        logger.debug("Instr to process: {}".format(instr))
        logger.debug("Match: {}".format(invoke_class_regex.search(instr).group(0)))
        target_class = invoke_class_regex.search(instr).group(0)
        target_class = target_class.strip().replace(";->", "")
        target_method = instr.split("->")[-1]
        target_method = target_method.strip()
        
        app_top_level = self.class_path.split("/")[1] # top level application directory
        logger.debug("Comparing: {}/{} -- {}".format(self.class_path, self.class_name, target_class)) 
        if "{}/{}".format(self.class_path, self.class_name) == target_class:
            #if "Lcom" in target_class and app_top_level in target_class and self.class_name in target_class:
            # local invocation
            # Check if it is invoke-direct (which seems to be the only local invocation we can handle) NOTE
            if "invoke-direct" in instr:
                self.invocations_local += [(method_id, block_id, target_method)]
                logger.debug("Adding {} -> {} as a local invocation".format(target_class, target_method))
            else:
                logger.debug("Ignoring {} -> {} since it is not a direct invocation".format(target_class, target_method))
        elif "Lcom" in target_class and app_top_level in target_class: # Added check for same top level (after com) as project
            # global invocation (add to list of files to process if necessary)
            self.invocations_global += [(method_id, block_id, target_class, target_method)]
            logger.debug("Adding {} -> {} as a global invocation".format(target_class, target_method))

            # Add to list to process if we haven't seen it before
            # clean the path (remove `L` add `smali` and the `.smali` extension)
            class_to_add = "smali/" + target_class[1:] + ".smali"
            if class_to_add not in state_file_list:
                state_file_list += [class_to_add]
            
        else:
            # library invocation
            self.invocations_lib += [(method_id, block_id, target_class, target_method)]
            logger.debug("Adding {} -> {} as a library invocation".format(target_class, target_method))

    def resolve_local_invocations(self):
        """Resolve local invocations at the end of the class
        Returns:
            A list of failed resolutions (if any)
        """
        logger.debug("Attempting to resolve local invocations: {}".format(self.invocations_local))
        report = []
        failed = False
        for src_method, src_block, target_method in self.invocations_local:
            resolved = False
            # Clean target method
            cleaned_target_method = target_method.split("(")[0]
            # Get the target method object
            for t_m_object in self.methods:
                logger.debug("Comparing: {} -- {}".format(t_m_object.method_name, target_method))
                if t_m_object.method_name == cleaned_target_method:
                    logger.debug("Match!")
                    # We have the target!
                    # get the first block as the target block
                    target_method_object = t_m_object
                    target_block_object = target_method_object.basic_blocks[0]
                    break
            else:
                logger.warning("Failed to get a target method object from {}".format(target_method))
                failed = True

            if not failed:
                # recover the source
                for s_m_object in self.methods:
                    if s_m_object.method_id == src_method:
                        # we have the src method as well!
                        src_method_object = s_m_object    
                        break
                else:
                    logger.warning("Failed to get source method object from {}".format(self.class_name))
                    failed = True

            if not failed:
                # get the correct block
                for src_block_object in src_method_object.basic_blocks:
                    if src_block_object.block_id == src_block:
                        # add the target method as a child of the src and the src as a parent of the target
                        src_block_object.add_child_block_id(target_block_object.block_id)
                        target_block_object.add_parent_block_id(src_block_object.block_id)
                        
                        # Add method links (for FCG)
                        src_method_object.add_call_out(target_method_object.method_id)
                        target_method_object.add_call_in(src_method_object.method_id)

                        # Check if the target returns anything and add an edge from last block of target to the src block if it does
                        if target_method_object.return_type != "V":
                            # TODO: Think about this - It's a CFG so shouldn't a void return also be linked?
                            # It does not return void, so add edge!
                            target_final_block_object = target_method_object.basic_blocks[-1]
                            target_final_block_object.add_child_block_id(src_block_object.block_id)
                            src_block_object.add_parent_block_id(target_final_block_object.block_id)
                            
                            # Add method links (if there is a non void return)
                            src_method_object.add_call_in(target_method_object.method_id)
                            target_method_object.add_call_out(src_method_object.method_id)


                        logger.debug("Successfully resolved local invocation: {} -> {}".format(src_method_object.method_name, target_method_object.method_name))
                        break
                else:
                    logger.warning("Failed to recover source block from {}".format(self.class_name))

        return report

class Graph():
    """A class for storing all of the information from multiple classes that make up the program
    (essentially stores the state)"""

    def __init__(self, file_list):
        """Initialise the Graph object
        Args:
            file_list: [str] - List of files to start processing (can be added to)
        """
        self.file_list       = file_list
        self.class_id        = 0
        self.method_id       = 0
        self.block_id        = 0
        self.instruction_id  = 0
        self.classes         = []
        self.ambiguous_calls = [] # stores tuple (instr_id, call) for easy resolution 
        self.method_lookup   = [] # stores all methods for easy cross class connections (method_name, method_id)

        # Keep track of the currently active structures
        self.active_class   = None
        self.active_method  = None
        self.active_block   = None
        
        # State flags
        self.ANNOTATION_FLAG = False
        self.FIELD_FLAG      = False
        self.SWITCH_FLAG     = False
        self.METHOD_FLAG     = False
        
        self.block_term      = True # Block termination flag (so we know if the instruction needs to be a leader)

    def add_class(self, smali_class):
        """Add smali class to the list of classes
        Args:
            smali_class: SmaliClass - The complete smali class to add
        """
        self.classes += [smali_class]

    def add_ambiguous_call(self, instr_id, call):
        """Add an ambigous call to the list to be resolved later
        Args:
            instr_id: int - The instruction id (for easy lookup during resolution)
            call: str - The target of the call which does not currently exist in the method list (this should be the full method name with class so we can find duplicates)
        """
        self.ambigous_calls += [(instr_id, call)]

    def add_method(self, method_name, method_id):
        """Add a method to the method list
        Args:
            method_name: str - The method name (for identification of any future calls)
            method_id: int - The id of the method if we need further details
        """
        self.method_lookup += [(method_name, method_id)]

    def add_file(self, file):
        """Add a file to process to the list of files in the state
        Args:
            file: str - The path to the file to process
        """
        self.file_list += [file]

    def resolve_global_invocations(self):
        """Resolve global invocations
        Returns:
            A list of global invocations that could not be resolved (if any)
        """
        report = []
        for smali_class in self.classes:
            # Check each class for global invocations
            for src_method_id, src_block_id, target_class_name, target_method_name in smali_class.invocations_global:
                failed_res = False
                # get the src method object
                for s_m in smali_class.methods:
                    if s_m.method_id == src_method_id:
                        # method object got!
                        src_method_obj = s_m
                        break
                else    :
                    report += ["{} Failed to resolve source method {} -> {}".format(smali_class.class_name, target_class_name, target_method_name)]
                    failed_res = True

                if failed_res:
                    break
                
                # get the target class object
                # clean up the target class name
                clean_target_class_name = target_class_name.split("/")[-1].replace(";", "")
                for target_class in self.classes:
                    if target_class.class_name == clean_target_class_name:
                        # found target class!
                        target_class_obj = target_class
                        break
                else:
                    report += ["{} Failed to resolve target class {} -> {}".format(smali_class.class_name, target_class_name, target_method_name)]
                    failed_res = True

                if failed_res:
                    break

                # at this point we have the target class and the source method
                # need to find the source block and the target method
                for src_bb in src_method_obj.basic_blocks:
                    if src_bb.block_id == src_block_id:
                        src_block = src_bb
                        break
                else:
                    report += ["{} Failed to resolve source block {} -> {}".format(smali_class.class_name, target_class_name, target_method_name)]
                    failed_res = True
                
                if failed_res:
                    break

                # get target method
                clean_target_method_name = target_method_name.split("(")[0]
                for t_m in target_class_obj.methods:
                    if t_m.method_name == clean_target_method_name:
                        target_method = t_m
                        break
                else:
                    report += ["{} Failed to resolve target method {} -> {}".format(smali_class.class_name, target_class_name, target_method_name)]
                    failed_res = True
                
                if failed_res:
                    break

                # We have everything we need so resolve!
                src_block.add_child_block_id(target_method.basic_blocks[0].block_id)
                target_method.basic_blocks[0].add_parent_block_id(src_block.block_id)
                
                src_method_obj.add_call_in(target_method.method_id)
                target_method.add_call_out(src_method_obj.method_id)

                # Check if the target returns
                if target_method.return_type != "V":
                    target_method.basic_blocks[-1].add_child_block_id(src_block.block_id)
                    src_block.add_parent_block_id(target_method.basic_blocks[-1].block_id)
                    src_method_obj.add_call_out(target_method.method_id)
                    target_method.add_call_in(src_method_obj.method_id)


        return report

    def resolve_library_invocations(self):
        """Resolve the invocations made to Android library functions
        Returns:
            A list of log messages for any invocations that could not be resolved
        """
        report = []
        generated_classes = [] # store the newly created library classes for quick access

        for smali_class in self.classes:
            # Check each class for library invocations
            failed_res = False
            for src_method_id, src_block_id, target_class_name, target_method_name in smali_class.invocations_lib:
                
                # search for target class
                for g_class in generated_classes:
                    # reconstruct full class name of the generated class
                    gen_class_name = g_class.class_path + "/" + g_class.class_name
                    logger.debug("Comparing generated: {} with target: {}".format(gen_class_name, target_class_name))
                    if gen_class_name == target_class_name:
                        logger.debug("Found match!")
                        target_class = g_class
                        break
                else:
                    target_class = SmaliClass(self.class_id, ".class public final {};".format(target_class_name))
                    self.class_id += 1
                    generated_classes += [target_class]

                # search for target method
                logger.debug("\tSearching for target method; {}".format(target_method_name))
                target_m_name, target_m_params, target_m_ret = Method.process_method_directive(".method T T {}".format(target_method_name)) # compare the components with the current method components
                for t_method in target_class.methods:
                    logger.debug("\tFound class method {} - target method: {}".format(t_method.method_name, target_m_name))
                    if t_method.method_name == target_m_name and t_method.param_types == target_m_params and t_method.return_type == target_m_ret:
                        target_method = t_method
                        logger.debug("\tFound match!")
                        break
                else:
                    logger.debug("\tFailed to find class method - adding now!")
                    target_method = Method(self.method_id, ".method T T {}".format(target_method_name))
                    self.method_id += 1
                    target_class.add_method(target_method)
                    
                    # Add dummy basic block with dummy instruction
                    dummy_instruction = Instruction(
                            "{} -> {}".format(target_class_name, target_method_name),
                            "DUMMY",
                            self.instruction_id,
                            0,
                            target_method.method_id,
                            target_class.class_id,
                            self.block_id)

                    dummy_block = BasicBlock(self.block_id, dummy_instruction)
                    self.block_id += 1
                    self.instruction_id += 1
                
                    target_method.add_basic_block(dummy_block)

                # Get the source method
                for s_method in smali_class.methods:
                    if s_method.method_id == src_method_id:
                        src_method_obj = s_method
                        break
                else:
                    report += ["{} Failed to resolve source method {}".format(smali_class.class_name, src_method_id)]
                    failed_res = True

                if failed_res:
                    break

                # get the source block
                for src_bb in src_method_obj.basic_blocks:
                    if src_bb.block_id == src_block_id:
                        src_block = src_bb
                        break
                else:
                    report += ["{} Failed to resolve source block {} -> {}".format(smali_class.class_name, target_class_name, target_method_name)]
                    failed_res = True
                
                if failed_res:
                    break

                # Link it all together!
                src_block.add_child_block_id(target_method.basic_blocks[0].block_id)
                target_method.basic_blocks[0].add_parent_block_id(src_block.block_id)

                # Check if the target returns
                if target_method.return_type != "V":
                    target_method.basic_blocks[-1].add_child_block_id(src_block.block_id)
                    src_block.add_parent_block_id(target_method.basic_blocks[-1].block_id)
        
        # push generated classes to the graph
        for gc in generated_classes:
            self.add_class(gc)

        return report
