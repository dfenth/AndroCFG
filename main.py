"""
Process the Smali file returning the class object with Basic Blocks
"""
class AppClass:
    """
    Represents a class of the application (usually a single smali file).
    Multiple App Classes can make up the whole application 
    """
    def __init__(self, class_uid, instr):
        """
        Initialisation method
        Args:
            class_uid (int): The unique class id
            instr (str): The initial instruction (.class directive)
        """
        self.uid = class_uid
        self.name = instr.split("/")[-1].replace(";", "")

def process_instructions(instructions):
    """
    Process the instructions from the smali file
    Args:
        instructions [str]: A list of smali instructions
    Returns:
        The class object with Basic Blocks
    """
    for line_num, instruction in enumerate(instructions):
        pass
