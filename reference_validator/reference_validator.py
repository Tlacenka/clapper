#!/usr/bin/env python
#coding=utf-8

from __future__ import with_statement, print_function

import argparse
import os
import pprint
import re
import sys
import six  # compatibility
import time
import yaml # pip install pyyaml

# only for Python 2.x
if sys.version_info[0] == 2:
    import nyanbar


class YAML_colours:
    ''' Code for colouring output '''
    BLUE      = '\033[94m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    ORANGE    = '\033[33m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    DEFAULT   = '\033[0m'

class YAML_tree_info:
    ''' Indicators of printed tree nodes '''
    OTHER = 0
    LAST = 1 # Last sibling
    ONLY = 2 # Only one child

class YAML_HotValidator:
    ''' Detects unused variables, invalid references.'''

    def __init__(self, arguments):
        ''' Finds *.yaml files based on entered arguments.
            arguments - dictionary with parsed arguments and their values
        '''

        # in environments, mappings, templates: all nodes with references to parent/children
        # in curr_nodes: currently validated nodes (DFS - depth-first search)

        # Save initial directory
        self.init_dir = os.getcwd()

        # List of YAML files to be checked + referenced children nodes
        self.environments = []
        self.mappings = []
        self.templates = []

        # Currently opened nodes
        self.curr_nodes = []

        # Applied parameters
        self.print_unused = arguments['unused']
        self.pretty_format = arguments['pretty_format']
        self.print_structure = arguments['print_tree']
        self.print_nyan = (sys.version_info[0] == 2) and arguments['nyan']
        self.sleep_time = 0.3
        self.printer = pprint.PrettyPrinter(indent=2)

        # Check HOT file (-f)
        abs_path = os.path.abspath(arguments['file'])
        if abs_path.endswith('yaml'):
            self.templates.insert(0, self.YAML_Hotfile(None, abs_path))
        else:
            print('Wrong template file suffix (YAML expected).')
            sys.exit(1)

        # Check environment files (-e)
        if arguments['environment']:
            for env in list(arguments['environment']):
                abs_path = os.path.abspath(env)
                if abs_path.endswith('yaml'):
                    self.environments.insert(0, self.YAML_Env(None, abs_path))


    class YAML_Types:
        ''' Enumerated reference get_ functions + properties:parameters reference. '''

        GET_RESOURCE  = 1 # get_resource
        GET_PARAM = 2     # get_param
        GET_ATTR = 3      # get_attr
        MISS_PROP  = 4    # parameter in file B does not have corresponding property in file A
        MISS_PARAM = 5    # property in file A does not have corresponding parameter in file B


    class YAML_Hotfile:
        ''' Class with attributes needed for work with HOT files. '''

        def __init__(self, parent_node, abs_path):
            ''' Node is initiated when being detected. '''

            self.path = abs_path

            self.parent = parent_node   # Parent node or nothing in the case of root node
            self.children = []          # Ordered children - by the moment of appearance in the code

            self.resources = []         # YAML_Resource list
            self.params = []            # list of YAML_Prop_Par
                                        # TODO exception for root template when checking properties values

            self.outputs = {}           # {name : <value structure>}

            self.structure = {}         # structure of YAML file
            self.ok = True

            self.invalid = []           # list of invalid references (YAML_Reference)


        def load_file(self, curr_nodes, templates, environments, curr_path):
            ''' Validates YAML file. '''

            # Add current node at the beginning
            curr_nodes.insert(0, self)

            # Open file
            try:
                with open(os.path.join(curr_path, self.path), 'r') as fd:
                    self.structure = yaml.load(fd.read())
            except IOError:
                print('File ' + self.path + ' could not be opened.')
                sys.exit(1)

            #print (self.structure)

            # Save all parameters names, resources and properties
            if 'parameters' in self.structure:
                for param in self.structure['parameters'].items():
                    self.params.append(YAML_HotValidator.YAML_Prop_Par(param, True))

            # Save name and structure of each resource
            if 'resources' in self.structure:
                for resource in self.structure['resources']:
                    self.resources.append(YAML_HotValidator.YAML_Resource(resource,
                                          self.structure['resources'][resource]))

            # Save outputs
            if 'outputs' in self.structure:
                for out in self.structure['outputs']:
                    self.outputs[out] = self.structure['outputs'][out]

            # Examine children nodes to get the full information about references
            for resource in self.resources:
                if resource.type.endswith('.yaml'):
                    templates.insert(0, YAML_HotValidator.YAML_Hotfile(self, resource.type))

                    # Add child
                    self.children.append(templates[0])
                    resource.child = templates[0]

                    # Start validating child
                    templates[0].load_file(curr_nodes, templates, environments,
                                           os.path.join(curr_path, os.path.dirname(self.path)))

                    # The whole subtree with root = current node is loaded

            # Remove node from current nodes after loading
            curr_nodes.remove(self)


        def validate_file(self, curr_nodes):
            ''' After loading information, validates references in file.'''

            # Add current node at the beginning
            curr_nodes.insert(0, self)

            # Iterate over sections (all children validated by now)
            for section, instances in six.iteritems(self.structure):
                # skip those without nested structures
                if type(instances) == dict:

                    # Iterate over instances (variables)
                    for variable, properties in six.iteritems(instances):
                        self.inspect_instances(properties, variable)

            # Remove node from current nodes after validation
            curr_nodes.remove(self)

        def inspect_instances(self, properties, name):
            ''' Check if all references to variables are valid.
                properties - structures containing instance properties and their values
                name       - name of referring instance
            '''

            if isinstance(properties, list):
                for element in properties:
                    if isinstance(element, dict) or isinstance(element, list):
                        self.inspect_instances(element, name)
            elif isinstance(properties, dict):
                # Check references, mark used variables
                for key, value in six.iteritems(properties):
                    if self.classify_items(key, value, name) is None:
                        self.inspect_instances(value, name)

        def classify_items(self, key, value, name):
           ''' If item contains reference, it is processed. '''

           if key == 'get_param':
               #print (value)
               return self.check_get_parameter(value, name)
           elif key == 'get_resource':
               return self.check_get_resource(value, name)
           elif key == 'get_attr':
               return self.check_get_attribute(value, name)
               return None

        def str_replace(self, kv):
            ''' Validates str_replace '''
            if ((kv is None) or (kv[0] != 'str_replace')):
               return None

            print (kv)

        def check_get_parameter(self, value, name):
            ''' Validates get_param
                value - referemce
                name - instance name
            '''
            if type(value) == list:
                
                error = None

                # Get root - parameter and its structure
                root = None
                for p in self.params:
                    if p.name == value[0]:
                        root = p
                if root is None:
                    error = value[0]

                # Get its value

                # Try validating based on property
                get_value = None
                #print (root.value)
                if root.value is not None:
                    if type(root.value) == str:
                        get_value = root.value
                    elif type(root.value) == dict:
                        kv = root.value.items()[0]
                        if self.classify_items(kv[0], kv[1], name) is None:
                            error = value[1]
                        elif ((kv[0] == 'str_replace') and
                              (self.str_replace(kv) is None)):
                            error = value[1]
                        else:
                           #get_value
                            pass
                else: # validate based on parameter only
                    if root.default is not None:
                        get_value = root.default
                    else:
                        error = value[1]
                #print (value)
   
                for ele in value[1:]:
                    if type(ele) == str:
                        if ele.isdigit(): # TODO points to smth in a group, check if it is a group
                            pass
                        else:
                            # Magic
                            error = ele
                    elif type(ele) == int: # in case of a list, which position
                        pass
                    elif type(ele) == dict: # nested get_
                        kv = ele.items()[0]
                        if not self.classify_items(kv[0]. kv[1], name):
                            error = ele
                    else:
                        error = ele

                if error is not None:
                    # Add it to invalid references
                    self.invalid.append(YAML_HotValidator.YAML_Reference(value[1], name,
                                        YAML_HotValidator.YAML_Types.GET_PARAM, None))
                    self.ok = False
   
            else:
                # Check if it is a pseudoparameter
                if value not in ['OS::stack_name', 'OS::stack_id', 'OS::project_id']:
                    if value not in [x.name for x in self.params]:
   
                        # Add it to invalid references
                        self.invalid.append(YAML_HotValidator.YAML_Reference(value, name,
                                             YAML_HotValidator.YAML_Types.GET_PARAM, None))
                        self.ok = False
   
                    else:
                        # Changes usage flag
                        par = [x for x in self.params if x.name == value][0]
                        if par.used == False:
                            par.used = True
            
        def check_get_resource(self, value, name):
            ''' Validates get_resource
                value - reference
                name - instance name
            '''
            if value not in [x.name for x in self.resources]:
                 # Add it to invalid references
                 self.invalid.append(YAML_HotValidator.YAML_Reference(value, name,
                                     YAML_HotValidator.YAML_Types.GET_RESOURCE, None))
                 self.ok = False
            else:
                for resource in self.resources:
                    if value == resource.name:
                        resource.used = True
                        break

        def check_get_attribute(self, value, name):
            ''' Validates get_attr
                value - reference
                name - instance name
            '''

            if type(value) == list:
                error = None

                if value[0] not in [x.name for x in self.resources]:
                   error = value[0]
   
                # if it is in a children node, check its first level of hierarchy
                elif [True for x in self.resources if ((x.name == value[0])
                                                       and x.type.endswith('.yaml'))]:
   
                    flag = False
                    for r in self.resources:
                        if r.name == value[0]:
                            for f in self.children:
                                if r.type == f.path:
                                    # outputs_list used in case of autoscaling group TODO ASG x RG
                                    if ((len(value) >= 3) and r.isGroup and
                                        (value[1] == 'outputs_list') and
                                        (value[2] in f.outputs.keys())):
                                        flag = True
               
                                    # mapped to outputs
                                    elif ((len(value) >= 2) and (value[1] in f.outputs.keys())):
                                        flag = True
               
                                    #resource.<name> used
                                    elif ((len(value) >= 2) and value[1].startswith('resource.')):
                                        string = value[1].split('.')
                                        if string[1] in [x.name for x in f.resources]:
                                            flag = True
                                    break
                            break
                    if not flag:
                        error = value[0]
                
                if error is not None:
                    self.invalid.append(YAML_HotValidator.YAML_Reference(error, name,
                                        YAML_HotValidator.YAML_Types.GET_ATTR, None))
                    self.ok = False

        def check_prop_par(self, parent, resource, environments):
            ''' Check properties against parameters and vice versa, tag used. '''

            # Get difference in names of properties and parameters
            differences = list(set([x.name for x in self.params]) ^ set([y.name for y in resource.properties]))

            for diff in differences:
                # Missing property for parameter
                if diff in [x.name for x in self.params]:
                    if [True for x in self.params if (x.name == diff) and (x.default is None)]:
                        self.invalid.append(YAML_HotValidator.YAML_Reference(diff, resource.name,
                                            YAML_HotValidator.YAML_Types.MISS_PROP, parent.path))
                        self.ok = False
                # Missing parameter for property
                elif diff in [x.name for x in resource.properties]:
                    self.invalid.append(YAML_HotValidator.YAML_Reference(diff, resource.name,
                                        YAML_HotValidator.YAML_Types.MISS_PARAM, self.path))
                    self.ok = False

            # Get all matches
            matches = list(set([x.name for x in self.params]) & set([y.name for y in resource.properties]))

            # Share YAML_Prop_Par for each match
            for m in matches:
                # Finds parameter and property
                prop = [x for x in resource.properties if x.name == m][0]
                for p in range(len(self.params)):
                    if self.params[p].name == m:
                        # Merges their attributes, prop and param share one object from now on
                        prop.merge(self.params[p])
                        self.params[p] = prop
                        break

    class YAML_Env:
        ''' Class with attributes needed for work with environment files. '''

        def __init__(self, parent_node, abs_path):
            self.path = abs_path

            # reference to parent and children nodes
            self.parent = parent_node
            self.children = []

            self.resource_registry = {} # original type: mapped type [, resource]
            self.params = {}            # additional parameters, only for root file -f
            self.params_default = {}    # default values, can replace property in property>param anywhere

            self.structure = {}
            self.invalid = []           # invalid parameter references

            self.ok = True


    class YAML_Resource:
        ''' Stores useful info about resource, its structure. '''
        def __init__(self, name, resource_struct):

            self.type = resource_struct['type']
            self.child = None    # child node
            self.name = name     # name of resource variable
            self.properties = [] # list of YAML_ParProp

            self.isGroup = False # is it a group type
            self.grouptype = ''

            if self.type in ['OS::Heat::AutoScalingGroup', 'OS::Heat::ResourceGroup']:
                self.isGroup = True

            props = []

            # If there are properties, save them
            # TODO save to YAML_Prop_Par, merge ASG and RG with ternary operator
            if 'properties' in resource_struct:
                # Type and properties of the individual resource
                if self.isGroup:
                    self.grouptype = self.type;
                    self.type = resource_struct['properties']['resource' if
                                self.grouptype == 'OS::Heat::AutoScalingGroup' else 'resource_def']['type']
                    for prop in resource_struct['properties']['resource' if
                                self.grouptype == 'OS::Heat::AutoScalingGroup' else 'resource_def']['properties'].items():
                        self.properties.append(YAML_HotValidator.YAML_Prop_Par(prop, False))
                else:
                    for prop in resource_struct['properties'].items():
                        self.properties.append(YAML_HotValidator.YAML_Prop_Par(prop, False))
                        #print (prop)

            self.used = False


    class YAML_Prop_Par:
        ''' Class for saving information about parameters and properties.
            Each parameter and its corresponding property share one. '''

        def __init__(self, structure, isPar):
            self.name = structure[0]    # name of parameter/property
            self.used = False           # flag of usage (reference)
            self.value = (None if isPar else structure[1]) # value (possibly structured)
            self.default = None
            self.type = None

            if isPar and ('type' in structure[1]):
                self.type = structure[1]['type']

            if isPar and ('default' in structure[1]):
                self.default = structure[1]['default']

        def merge(self, obj):
            ''' Merges 2 objects, uses attributes of the second object if they are defined.
                obj = parameter
            '''
            # Objects must have the same name
            if self.name != obj.name:
                return

            self.used = self.used or obj.used

            if obj.value is not None:
                self.value = obj.value

            if obj.default is not None:
                self.default = obj.default

            if obj.type is not None:
                self.type = obj.type

    class YAML_Reference:
        ''' Saves all invalid references for output. In YAML_Hotfile. '''

        def __init__(self, referent, element, ref_type, parent):
            self.referent = referent # name of referred element
            self.element = element   # in which resource was reference realized
            self.type = ref_type     # type of referred attribute (YAML_Types)
            self.parent = parent     # used in property reference


    def load_environments(self):
        ''' Goes through all environment files, saves information about them. '''

        if not self.environments:
            return

        for env_node in self.environments:
            try:
                with open(env_node.path, 'r') as fd:
                    env_node.structure = yaml.load(fd.read())
            except IOError:
                print('File ' + env_node.path + ' could not be opened.')
                sys.exit(1)

            # Add to currently validated files
            self.curr_nodes.insert(0, env_node)

            # Save mappings
            if 'resource_registry' in env_node.structure:
                for origin, custom in six.iteritems(env_node.structure['resource_registry']):
                    if type(custom) == str:
                        env_node.resource_registry[origin] = custom
                    elif origin == 'resources':
                        # Find if there is any mapping (hooks etc are not important)
                        for res in env_node.structure['resource_registry']['resources'].keys():
                            for key, value in six.iteritems(env_node.structure['resource_registry']['resources'][res]):
                                # Add indirect mapping using regexp - multiple indentations
                                if (type(value) == str) and (value.endswith('.yaml')):
                                    env_code.resource_registry[key] = [value, res]

            # Save additional parameters + parameters with default values
            if 'parameters' in env_node.structure:
                for par in list(env_node.structure['parameters'].keys()):
                    env_node.params[par] = False

            if 'parameter_defaults' in env_node.structure:
                for par in list(env_node.structure['parameter_defaults'].keys()):
                    env_node.params_default[par] = False

            # Create HOT files with mapped files - TODO regexp mapping
            for child in list(env_node.resource_registry.values()):
                if ((type(child) == str and child.endswith('.yaml')) or
                    ((type(child) == list) and child[0].endswith('.yaml'))):

                    # Is a file is created already as a root, no need for redundancy
                    found = False
                    for m in self.mappings:
                        if ((m.path == child) and (m.parent in self.environments)):
                            env_node.children.insert(0, m)
                            found = True
                            break

                    if not found:
                        env_node.children.insert(0, self.YAML_Hotfile(env_node, child))
                        self.mappings.append(env_node.children[0])

            # Remove from currently validated files
            self.curr_nodes.remove(env_node)


    def add_mappings(self):
        ''' Add all files mapped to resources as children in parent node. '''
        # TODO regexp mappings

        for hot in self.templates + self.mappings:
            for res in hot.resources:

                # If a mapped file exists
                flag = False
                for env in self.environments:
                    for origin, mapped in six.iteritems(env.resource_registry):

                        # Finds mapped file if the mapping is designated for the resource
                        if ((res.type == origin) and
                            ((type(mapped) == str) or (mapped[1] == res.name))):

                            # Assign it to resource
                            for m in self.mappings:
                                if (((type(mapped) == str) and (m.path == mapped)) or
                                    ((type(mapped) == list) and (m.path == mapped[0]))
                                    and (m.parent == env)):
                                    res.child = m
                                    flag = True
                                    break
                        if flag:
                            break
                    if flag:
                        break


    def validate_env_params(self):
        ''' Checks parameters section of environment files. '''

        # Check parameters section
        for env in self.environments:
            for par in list(env.params.keys()):
                if par in list(self.templates[-1].params.keys()):
                    env.params[par] = True

        # Check parameter_defaults section
        for env in self.environments:
            for par in list(env.params_default.keys()):
                for hot in self.templates:
                    if par in [x.name for x in hot.params]:
                        env.params_default[par] = True
                        break
                for hot in self.mappings:
                    if par in [x.name for x in hot.params]:
                        env.params_default[par] = True
                        break


    def validate_properties(self, template):
        ''' Validate properties x parameters in tree of templates. '''

        # Add current node at the beginning
        self.curr_nodes.insert(0, self)

        # Go through all resources in current template
        for resource in template.resources:
            # Continue with child nodes
            if resource.child is not None:
                resource.child.check_prop_par(template, resource,
                                              self.environments)
                self.validate_properties(resource.child)

        # Remove node from current nodes after validation
        self.curr_nodes.remove(self)

        # TODO get value of properties for future use


    def validate_references(self, root):
        ''' Validates references in file '''

        # Validate parent
        root.validate_file(self.curr_nodes)
        #print(root.path)

        # Go through all resources in current template
        for resource in root.resources:
            # Continue with child nodes
            if resource.child is not None:
                resource.child.validate_file(self.curr_nodes)
                self.validate_references(resource.child)

    def print_tree(self, root, root_position, indent, branch_list):
        ''' Prints tree structure of templates '''

        # Print higher branches
        if (len(branch_list) and (root_position != YAML_tree_info.ONLY)):
            cur_indent = 0
            print('')
            for i in branch_list:
                print ((i-cur_indent-1) * '   ' + '│   ', end="")
                cur_indent = i
            print ((indent-cur_indent-1) * '   ', end="")
        elif root_position != YAML_tree_info.ONLY:
            print ('\n' + (indent-1) * '   ', end="")
                
        # Print child node
        if indent > 0:
            if root_position == YAML_tree_info.ONLY:
                print (' ── ' + root.path, end="")
            elif root_position == YAML_tree_info.OTHER:
                print ('├─ ' + root.path, end="")
            elif root_position == YAML_tree_info.LAST:
                print ('└─ ' + root.path, end="")
        else:
            print(root.path, end="")

        indent = indent + 1

        # Find out first and last child/sibling
        lastindex = None
        firstindex = None
        for r in root.resources:
            if r.child is not None:
                lastindex = root.resources.index(r)
                if firstindex is None:
                    firstindex = root.resources.index(r)

        child_position = (YAML_tree_info.ONLY if ((lastindex is not None) and (lastindex == firstindex)) else YAML_tree_info.OTHER)
        branch_list = branch_list + ([indent-1] if root_position != YAML_tree_info.ONLY else [])

        # Print subtrees of children
        for r in root.resources:
            if r.child is not None:
                if ((child_position != YAML_tree_info.ONLY) and (root.resources.index(r) == lastindex)):
                    child_position = YAML_tree_info.LAST

                self.print_tree(r.child, child_position, indent, branch_list)


    def print_output(self):
        ''' Prints results of validation for all files + additional info. '''

        # Environments
        if self.environments:
            if self.pretty_format:
                print(YAML_colours.ORANGE + YAML_colours.BOLD + YAML_colours.UNDERLINE +
                      'Environments:' + YAML_colours.DEFAULT)
            else:
                print('Environments:')

            # Print total
            if self.pretty_format:
                print(YAML_colours.BOLD + 'Total: ' + str(len(self.environments)) +
                      YAML_colours.DEFAULT)
            else:
                print ('Total: ' + str(len(self.environments)))
            print('')

            for env in self.environments:

                # Print title
                if self.pretty_format:
                    print(YAML_colours.BOLD + YAML_colours.UNDERLINE +
                          'File ' + YAML_colours.BLUE +
                          os.path.relpath(env.path, self.init_dir) +
                          YAML_colours.DEFAULT)
                else:
                    print('File ' + os.path.relpath(env.path, self.init_dir))
                print('')

                # Parameters section
                if False in list(env.params.values()):
                    env.ok = False
                    if self.pretty_format:
                         print (YAML_colours.BOLD + 'Parameters without match in root template:' +
                                YAML_colours.DEFAULT)
                    else:
                         print ('Parameters without match in root template:')
                    for par in [x for x in list(env.params.keys())
                                if env.params[x] == False]:
                        if self.pretty_format:
                            print ('- ' + YAML_colours.YELLOW + par + YAML_colours.DEFAULT)
                        else:
                            print ('- ' + par)
                    print('')

                # Parameter_defaults section (optional)
                if self.print_unused and (False in list(env.params_default.values())):
                    if self.pretty_format:
                        print (YAML_colours.BOLD + 'Parameter defaults without match:' +
                               YAML_colours.DEFAULT)
                    else:
                        print ('Parameter defaults without match:')

                    for par in [x for x in list(env.params_default.keys())
                                if env.params_default[x] == False]:
                        if self.pretty_format:
                            print ('- ' + YAML_colours.YELLOW + par +
                                    YAML_colours.DEFAULT)
                        else:
                            print ('- ' + par)
                    print('')

                # Print file status as OK if there were no problems
                if env.ok:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Status: ' + YAML_colours.GREEN +
                              'OK' + YAML_colours.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Status: ' + YAML_colours.RED +
                              'FAILED' + YAML_colours.DEFAULT)
                    else:
                        print('Status: FAILED')

                print('\n\n')


        # HOT Files and mappings
        rev_templates = list(reversed(self.templates))
        for hot in [x for x in [rev_templates, list(reversed(self.mappings))] if len(x)]:
            if self.pretty_format:
                print(YAML_colours.ORANGE + YAML_colours.BOLD + YAML_colours.UNDERLINE +
                      ('HOT Files:' if hot == rev_templates else 'Mapped HOT Files:') +
                      YAML_colours.DEFAULT)
            else:
                print(('HOT Files:' if hot == rev_templates else 'Mapped HOT Files:'))

            # Print total
            if self.pretty_format:
                print(YAML_colours.BOLD + 'Total: ' + str(len(self.templates) if hot == rev_templates else len(self.mappings)) +
                      YAML_colours.DEFAULT)
            else:
                print ('Total: ' + str(len(self.templates) if hot == rev_templates else len(self.mappings)))
            print('')

            for node in hot:

                # Print title
                if self.pretty_format:
                    print(YAML_colours.BOLD + YAML_colours.UNDERLINE + 'File ' +
                          YAML_colours.BLUE + node.path + YAML_colours.DEFAULT)
                else:
                    print('File ' + node.path)

                # Print parent node for better navigation
                if self.pretty_format:
                    print(YAML_colours.BOLD + 'Parent: ' + YAML_colours.DEFAULT +
                          (os.path.relpath(node.parent.path, self.init_dir) if (node.parent is not None) else 'None (root)'))
                else:
                    print('Parent: ' + (os.path.relpath(node.parent.path, self.init_dir) if (node.parent is not None) else 'None (root)'))
                print('')

                # Print children nodes
                if [True for x in node.resources if x.child is not None]:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Children:' + YAML_colours.DEFAULT)
                    else:
                        print('Children:')

                    for res in node.resources:
                        if res.child is not None:
                            print('- ' + res.child.path)
                    print('')

                # Invalid references
                if node.invalid:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Invalid references:' + YAML_colours.DEFAULT)
                    else:
                        print('Invalid references:')

                    for ref in node.invalid:
                        if ref.type == self.YAML_Types.GET_RESOURCE:
                            if self.pretty_format:
                                print ('Resource ' + YAML_colours.YELLOW + ref.referent +
                                       YAML_colours.DEFAULT + ' referred in ' + YAML_colours.YELLOW +
                                       ref.element + YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Resource ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        elif ref.type == self.YAML_Types.GET_PARAM:
                            if self.pretty_format:
                                print ('Parameter ' + YAML_colours.YELLOW + ref.referent +
                                       YAML_colours.DEFAULT + ' referred in ' + YAML_colours.YELLOW +
                                       ref.element + YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Parameter ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        elif ref.type == self.YAML_Types.GET_ATTR:
                            if self.pretty_format:
                                print ('Instance ' + YAML_colours.YELLOW + ref.referent +
                                       YAML_colours.DEFAULT + ' referred by ' + YAML_colours.YELLOW +
                                       'get_attr' + YAML_colours.DEFAULT + ' in ' + YAML_colours.YELLOW +
                                       ref.element + YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Instance ' + ref.referent + ' referred by get_attr in ' +
                                       ref.element + ' is not declared.')

                        elif ref.type == self.YAML_Types.MISS_PROP:
                            if self.pretty_format:
                                print('Parameter ' + YAML_colours.YELLOW + ref.referent + YAML_colours.DEFAULT +
                                      ' has no corresponding default or property in ' +  YAML_colours.YELLOW +
                                      ref.element + YAML_colours.DEFAULT + ' in ' +
                                      YAML_colours.YELLOW + os.path.relpath(ref.parent, self.init_dir) + YAML_colours.DEFAULT + '.')
                            else:
                                print('Parameter ' + ref.referent + ' has no corresponding default or property in' +
                                      ref.element + ' in ' + os.path.relpath(ref.parent, self.init_dir) + '.')

                        elif ref.type == self.YAML_Types.MISS_PARAM:
                            if self.pretty_format:
                                print('Property ' + YAML_colours.YELLOW + ref.referent + YAML_colours.DEFAULT +
                                      ' has no corresponding parameter in ' + YAML_colours.YELLOW +
                                      os.path.relpath(ref.parent, self.init_dir) + YAML_colours.DEFAULT + '.')
                            else:
                                print('Property ' + ref.referent + ' has no corresponding parameter in ' +
                                      os.path.relpath(ref.parent, self.init_dir) + '.')
                    print('')

                # Unused parameters (optional) ??
                if self.print_unused and (False in [x.used for x in node.params]):
                    if self.pretty_format:
                        print(YAML_colours.BOLD +  'Unused parameters:' + YAML_colours.DEFAULT)
                    else:
                        print('Unused parameters:')

                    for par in node.params:
                        if par.used == False:
                            if self.pretty_format:
                                print('- ' + YAML_colours.YELLOW + par.name + YAML_colours.DEFAULT)
                            else:
                                print('- ' + par.name)
                    print('')

                # Print unused resources (optional)
                if (self.print_unused) and [True for x in node.resources if not x.used]:
                    if (self.pretty_format):
                        print(YAML_colours.BOLD + 'Resources without reference:' +
                              YAML_colours.DEFAULT)
                    else:
                        print('Resources without reference:')

                    for resource in node.resources:
                        if resource.used == False:
                            if self.pretty_format:
                                print('- ' + YAML_colours.YELLOW + resource.name + YAML_colours.DEFAULT +
                                      ' (' + resource.type + ')')
                            else:
                                print('- ' + resource.name)
                    print('')

                # Print file status as OK if there were no problems
                if node.ok:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Status: ' + YAML_colours.GREEN +
                              'OK' + YAML_colours.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(YAML_colours.BOLD + 'Status: ' + YAML_colours.RED +
                              'FAILED' + YAML_colours.DEFAULT)
                    else:
                        print('Status: FAILED')

                print('\n')

        if self.print_structure:
            if self.pretty_format:
                print(YAML_colours.ORANGE + YAML_colours.BOLD + YAML_colours.UNDERLINE +
                      'Structure:' + YAML_colours.DEFAULT)
            else:
                print('Structure:')

            self.print_tree(self.templates[-1], YAML_tree_info.ONLY, 0, [])
            print('\n')

    def run(self):
        ''' Runs validator '''

        # Initialize nyanbar
        if self.print_nyan:
            progress = nyanbar.NyanBar(tasks=6)

        # Load environments to get mappings
        self.load_environments()

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Load HOTs in mappings
        # All mappings are at the beginning, followed by children nodes
        for hot in list(reversed(self.mappings)):
            if hot.parent in self.environments:
                hot.load_file(self.curr_nodes, self.mappings,
                                  self.environments, os.path.join(self.init_dir,
                                  os.path.dirname(hot.parent.path)))
            else:
                break

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Load HOTs: change to its directory, validate -f
        self.templates[0].load_file(self.curr_nodes, self.templates,
                                             self.environments,
                                             os.path.join(self.init_dir,
                                             os.path.dirname(self.templates[0].path)))

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Also add mapped files as children once there is a full structure of files
        # (if done earlier, some mapped types used in mapped files could be skipped)
        self.add_mappings()

        # Check environment parameters against fully loaded HOT structure
        self.validate_env_params()

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Check properties x parameters
        self.validate_properties(self.templates[-1])

        for hot in list(reversed(self.mappings)):
            if hot.parent in self.environments:
                self.validate_properties(hot)

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Validate references
        self.validate_references(self.templates[-1])

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)
            progress.finish()


def main():

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--unused', action='store_true',
                        help='When true, prints all unused resources/parameters.')
    parser.add_argument('-p', '--pretty-format', action='store_true',
                        help='When true, provides colourful output')
    parser.add_argument('-t', '--print-tree', action='store_true',
                        help='When true, output contains template structure')
    parser.add_argument('-e', '--environment', metavar='path/to/environment', nargs='+',
                        help='Environment files to be used.')
    parser.add_argument('-f', '--file', metavar='path/to/file',
                        help='HOT file to be used.')
    parser.add_argument('-n', '--nyan', action='store_true',
                        help='When true, prints nyanbar.')

    # Initialize validator
    validator = YAML_HotValidator(vars(parser.parse_args()))

    # Run validator
    validator.run()

    # Print results
    validator.print_output()

    sys.exit(0)

if __name__ == '__main__':
    main()
