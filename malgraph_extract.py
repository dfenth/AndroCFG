"""
Code for the extraction of MalGraph specific data
"""

import os, json
from structures import Method
from config import logger

def extract_library_functions(state, count_path=""):
    """Count the different library functions that are called
    appending the count (and adding new values) to a json file
    Args:
        state: Graph - The program state graph
        count_path: str - The path to the json library and count file (if one exists)
    """
    
    # Load the counts from file, if none exist create a new one
    if count_path != "" and os.path.exists(count_path):
        with open(count_path, "r") as count_file:
            count_data = json.load(count_file)

    else:
        count_data = {}

    for smali_class in state.classes:
        # Check each class for library invocations
        failed_res = False
        for _, _, target_class_name, target_method_name in smali_class.invocations_lib:
            
            # search for target class
            for g_class in state.classes:
                # reconstruct full class name of the generated class
                gen_class_name = g_class.class_path + "/" + g_class.class_name
                logger.debug("Comparing generated: {} with target: {}".format(gen_class_name, target_class_name))
                if gen_class_name == target_class_name:
                    logger.debug("Found match!")
                    target_class = g_class
                    break
            else:
                logger.warning("Failed to resolve library class (MalGraph)")

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
                logger.warning("\tFailed to find class method")
            
            # Add the method to the library list!
            identifier = "{}-{}".format(gen_class_name, target_method.method_name)
            try:
                count_data[identifier]['count'] += 1
            except:
                count_data[identifier] = {'count':1, 'method_id':target_method.method_id}

    count_json = json.dumps(count_data)

    if count_path == "":
        count_path = "libcount.json"

    with open(count_path, "w") as json_file:
        json_file.write(count_json)

