# CFGext
This project contains python code for CFG extraction from the [Smali intermediate langauge](https://github.com/JesusFreke/smali) which is commonly used for Android app disassembly. This README intends to document the code as much as possible to allow for easy extension and/or adaptation.

### Requirements
This code was written in python 3.x (3.9 specifically, but any version should work). The only required library is [xmltodict](https://github.com/martinblech/xmltodict) (`pip install xmltodict`) for the manifest file processing.

### Usage
This program operates on apps that have already been disassembled using [apktool](https://ibotpeaches.github.io/Apktool/) with the decode `d` option to decode the manifest file (so the command would be `apktool d <app-to-disassemble>`). This should produce a directory that CFGext can interact with.

To run CFGext use the `extract.py` file with the following command line options (addin the `-h` or `--help` flag will display these options).
- `-d`/`--dir` - The directory of the disassembled application to process.
- `-o`/`--out` - The directory where any output graphs should be placed.
- `-f`/`--format` - `{coo, dot}` the graph output format. `coo` is useful for downstream ML tasks (e.g. Graph Neural Networks etc.) whereas `dot` is useful for graph visualisation.
- `-t`/`--type` - `{fcg, cfg}` the type of graph to output. The `cfg` option will produce the CFG of the entire (designed) program whereas `fcg` will output the interactions between function calls only.

If a `dot` file is produced it can be compiled to an image using [graphviz](https://graphviz.org/) using a command such as `dot -Tsvg <graph-file>.dot -o <output-image-name>.svg`. Using the `svg` format is recommended since the graphs can get large!


### File overview
**config.py** - Contains configuration information for the logger which is used to keep track of code execution. By default the logger is set to only show warning level issues and above because a lot of information is generated otherwise. The logger can also be set to debug for a complete walkthrough of the code execution (which is useful for debugging incorrect graphs), or info which logs the code execution at a higher level (not as detailed as debug).

**extract.py** - The start of the code execution. This starts by making a call to process the Android manifest file followed by a creation of the process state. The code then loads the next smali file in the list, takes the instruction, checks for a directive and then processes the instruction further. Once the file has been processed local method calls are resolved then when all files have been processed the global and library calls are resolved. Finally the output is produced which takes the form of a CFG or FCG in [dot](https://graphviz.org/) or [COO](https://en.wikipedia.org/wiki/Sparse_matrix#Coordinate_list_(COO)) format.

**output_graph.py** - Contains code to format the graph into an output of the specified type and extract feature vectors.

**process_instruction.py** - Processes each smali instruction depending on it's type as defined by the [Dalvik opcode or directives](https://source.android.com/devices/tech/dalvik/dalvik-bytecode).

**process_manifest.py** - Extracts information from the manifest file such as the classes associated with activities (which are added to a list to be processed) and the permissions the app requests.

**structures.py** - Contains the internal classes that are used to create the CFG of the application along with edge resolution code to connect graph vertices correctly.

### Method
This section describes how a CFG is created from the smali code files from start to finish.
When a valid folder is passed to `extract.py` it opens the `AndroidManifest.xml` file and processes it. The activity files within the manifest describe all of the valid ways that an app can be started by the user (e.g. tapping the app icon, another app calling for a specific task which this app can respond to etc.). These activities usually correspond to different classes within the project, therefore, we extract the class along with the path to it from the manifest and add it to a list of files to process when creating our graph. 
With the starting files extracted we load the first one in the list and process all of the instructions contained within the file. 
We start by looking for any active directives which would change the way we interpret the instruction:
- `.annotate` - Consists of a number of lines which denote class metadata such as bytecode versions, class field names and class method names in a very loose format.
- `.field` - Describes a class field which can be a single line or multiple lines (often with further annotations nested within).
- `.packed-switch`/`.sparse-switch` - Details the labels associated with a switch statement along with the location of the value to compare to.
- `.method` - The most common directive which contains the Dalvik opcode to process and create the CFG from.

We then process the instruction within the appropriate context.
If the `.annotate` directive is active we do not process the instruction any further and add it to the annotation data of a method if the method directive is active, field if the field directive is active or the class  if no other directives are active.
If the `.field` directive is active we add the unprocessed instruction to the class field data.
If  `.packed/sparse-switch` is active we fetch the previous instruction which will be a label which acts as an alias for all of the following labels. We add all labels to a label alias dictionary for resolution at the end of the class.
If `.method` is active we process the instruction further depending on it's type:
- `.method` - If we have the `.method` directive then we're starting a new method, so we push any currently active basic blocks and methods to the class start a new method and basic block for the next instructions.
- `.end method` - This is the last instruction in the method, so we resolve any labels we have come across within the method (internal `goto` and `:label` instructions) which allows us to build connections between basic blocks that are local to the method itself.
- `:label` - A label instruction is a leader, so we end the currently active basic block (pushing it to the method) and start a new one with the label as the first  instruction.
- `return` - A return call from the current method. Returns can happen from any part of a method (with code coming after it e.g. it could be part of a conditional) therefore we do not end the currently active method. The return call is a basic block terminator though, which means the instruction after this one will be a part of a new basic block, therefore, we set a termination flag and continue.
- `goto` - Is an unconditional statement which changes the control flow of the program, therefore `goto` is a basic block terminator. It specifies a label to jump to, but there is no guarantee we've seen the label at this point, therefore we add the `goto` to a list of label calls which are resolved at the end of the method.
- `if` - Very similar to `goto` except the basic block this instruction belongs to is the parent of both the next instruction in the sequence and the specified target label. 
- `invoke` - An invocation of a method which can be local (intra-class), global (inter-class) or library. Local invocations are resolved at the end of the class with global and library functions being resolved once all relevant classes within the application have been processed. 
- `line` - Are instructions added by the disassembly process. We ignore these as they have no relevance to the program execution.
All other instructions are caught and added to the basic block without further processing since they do not contribute to the structure of the graph. Note that this is a very flexible system, so if any other instructions were deemed important, they can be added in a very easy way with minimal impact on the rest of the processing.

Once the entire class has been processed (we reach the end of file) we resolve the global and library calls. In the CFG generation process we differentiate between global and library calls with the idea the global calls are within the application that the developer has written whereas library calls target library functions which have been written by Google. We add the class of any global calls to the list of files to process to generate as part of the CFG to ensure we have as much coverage of the developer application as possible. We do not expand the library functions into CFGs to have a managable (but still large) CFG.

We can then extract the data from the generated CFG and save it to a COO or dot format for further processing. To do this we iterate over all generated basic blocks. In the case of generating a dot file, we take all of the connections between the basic blocks along with the code which makes up each block and store them to file. For the COO generation we iterate over all basic blocks again, but we summarise each block using a feature vector function (which can be easily changed). We store the feature vectors along with the sparse representations for a feature and adjacency matrix to file so the graph can be re-created at a later data (useful for downstream ML methods).
