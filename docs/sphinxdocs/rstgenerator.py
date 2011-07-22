#! /usr/bin/python

import sys, re, os

def generateFile(input_directory, file_name, output_directory,
                 package_heirarchy=None, module_name=None):
    """Generate a rst file telling sphinx to just generate documentation
    for the public interface automatically.  Output will be written to
    *file_name*.rst in the current directory.
    
    :param input_directory: a string specifying the directory containing the 
       source code file
    :param file_name: the name of the python source code file to generate
       a sphinx rst file describing
    :param ouput_directory: a string specifying the directory where
       the generated rst file should be placed.  If *output_directory* does
       not already exist, it will be created
    :param package_heirarchy: a list of strings, where each name is
       the name of a package, in the order of the hierarchy
    :param module_name: the name of the module. If not given, the .py is 
       removed from *file_name* to produce the module_name
    """
    #Stick all output into a list of strings, then just join it and output
    #it all in on go.
    output = []
    
    # Create the output directory if it doesn't already exist. Note that
    # if the directory is created between the check and the creation, it 
    # might cause issues, but I don't think this likely at all to happen
    if not os.path.exists(output_directory):
        try:
            os.makedirs(output_directory)
        except OSError as e:
            print "Error creating the output directory"
            print e.args

    try:
        #Open the file
        f = open(os.path.join(input_directory, file_name), 'r')
    
        #Do the module output
        if not module_name:
            module_name = re.search('(\w+).py$', file_name).group(1)

        #Append the package names, if there are any
        full_module_name = module_name
        if package_heirarchy:
            full_module_name = '.'.join(package_heirarchy) + '.' + module_name
    
        output.append(full_module_name)
        output.append('=' * len(full_module_name))
        output.append('.. automodule:: %s\n' % full_module_name)
        
        #Read the file, and do output for classes
        class_reg = re.compile('^class (\w+)')
        func_reg = re.compile('^def ((?:[a-zA-Z0-9]+_)*[a-zA-Z0-9]+)')
        
        #We don't need a blank line between autofunction directives, but we do
        #need one between autofunctions and headings etc. for classes.  This
        #keeps track if we're switching from autofunctions to classes, so we
        #can add that blank line.
        finding_functions = False
        
        for line in iter(f):
            #Search for classes
            match = class_reg.match(line)
            if match is not None: 
                if finding_functions:
                    output.append('')
                    finding_functions = False
                class_name = match.group(1)
                output.append(class_name)
                output.append('-' * len(class_name))
                output.append('''.. autoclass:: %s
           :members:
           :show-inheritance:
        
           ''' % class_name)
        
        
            #Search for top level functions
            else:
                match = func_reg.match(line)
                if match is not None:
                    func_name = match.group(1)
                    output.append('.. autofunction:: ' + func_name)
                    finding_functions = True
        f.close()

    except IOError as e:
        print "Error opening the input file : ", os.path.join(input_directory, file_name)
        print e.args[1]

    else:
        #Write the output
        try:
            output_file_name = os.path.join(output_directory, module_name) + '.rst'
            f = open(output_file_name, 'w')
            f.write('\n'.join(output))
            
            
        except IOError as e:
            print "Error opening the output file : ", output_file_name
            print e.args[1]

                
def generateIndex(module_list, output_directory):
    """Create an index.rst file for sphinx in the given directory.

    :param module_list: a list of the names of the modules to list in
       the index file
    :param output_directory: the directory to create the index file in
    """

    #Sort the module_list
    module_list.sort()

    try:
        #open the file
        f = open(os.path.join(output_directory, 'index.rst'), 'w')
    
        #Do the output
        f.write(""".. Yum documentation master file, created by
   sphinx-quickstart on Mon Jun 27 14:01:20 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Yum's documentation!
===============================

Contents:

.. toctree::
   :maxdepth: 2

   """)
        f.write('\n   '.join(module_list))
        f.write("""

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
""")

    except IOError as e:
        print "Error opening the output file."
        print e.args[1]


def generateAll(source_directory, output_directory):
    #Verify that both the source and output directories exist


    # Keep a set of file names that are packages.  This is 
    # useful so that later we will be able to figure out full
    # module names.
    packages = set()

    # Keep a list of tuples containing python module names and
    # relative paths, so that we can build the index file later
    modules = []

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(source_directory, topdown=True):
        
        # print dirpath
        # print dirnames
        # print filenames
        # print

        # Add the curent directory to packages if __init__.py exists
        if '__init__.py' in filenames:
            packages.add(dirpath)

        # Find the heirarchy of packages that we are currently in
        package_heirarchy = []
        #Recurse up to the root
        dirpath_i = dirpath
        while dirpath_i != '/':
            if dirpath_i in packages:
                dirpath_i, tail = os.path.split(dirpath_i)
                package_heirarchy.insert(0, tail)
            else:
                break

        # Find the relative output directory, mirroring the input
        # directory structure
        relative_output_directory = ''
        if not os.path.samefile(dirpath, source_directory):
            relative_output_directory = os.path.relpath(dirpath, source_directory)
        
        # Don't recurse into directories that are hidden, or for docs
        for directory in dirnames:
            if directory == "docs" or directory.startswith("."):
                dirnames.remove(directory)

        # Generate the rst for a file if it is a python source code file
        for file_name in filenames:
            # Skip file names that contain dashes, since they're not
            # valid module names, so we won't be able to import them
            # to generate the documentation anyway
            if '-' in file_name:
                continue

            if file_name.endswith('.py'):
                module_name = file_name.partition('.')[0]
                modules.append(os.path.join(relative_output_directory, 
                                            module_name))
                generateFile(dirpath, file_name, 
                             os.path.join(output_directory, relative_output_directory),
                             package_heirarchy, module_name)

        
    
    # Create the index.rst file
    generateIndex(modules, output_directory)

if __name__ == "__main__":
    generateAll(os.getcwd(), os.getcwd())
