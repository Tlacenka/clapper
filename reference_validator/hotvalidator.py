#!/usr/bin/env python
#coding=utf-8

# File: hotvalidator.py
# Brief: Contains class HotValidator for validating references
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import os
import pprint
import sys
import six  # compatibility
import time
import yaml # pip install pyyaml

import enum
import hotfile
import hotclasses

# import nyanbar if available
try:
    import nyanbar
except ImportError:
    nyanbar = None

class HotValidator:
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
        self.parameters = {}

        # Currently opened nodes
        self.curr_nodes = []

        # Applied parameters
        self.print_unused = arguments['print_unused']
        self.pretty_format = arguments['pretty_format']
        self.print_structure = arguments['print_tree']
        self.print_nyan = nyanbar and arguments['nyan']
        self.sleep_time = 0.3
        self.printer = pprint.PrettyPrinter(indent=2)

        # Check HOT file (-f)
        abs_path = os.path.abspath(arguments['template_file'])
        if abs_path.endswith('yaml'):
            self.templates.append(hotfile.HotFile(None, abs_path))
        else:
            print('Wrong template file suffix (YAML expected).')
            sys.exit(1)

        # Check environment files (-e)
        if arguments['environment_file']:
            for env in list(arguments['environment_file']):
                abs_path = os.path.abspath(env)
                if abs_path.endswith('yaml'):
                    self.environments.append(hotclasses.Environment(None, abs_path))

        # Additional parameters (-P) separately / separated by ';'
        if arguments['parameters']:
            # ';' used
            if (len(arguments['parameters']) == 1) and (';' in arguments['parameters'][0]):

                # Split to key value pairs
                par_list = arguments['parameters'][0].split(';')
            else:
                par_list = arguments['parameters']

            # Assign KV to self.parameters
            for par in par_list:
                kv = par.split('=')
                self.parameters[kv[0]] = kv[1]


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
            except Exception as err:
                print('ERROR in file ' + env_node.path + ': ' + str(err), file=sys.stderr)
                sys.exit(1)

            # Add to currently validated files
            self.curr_nodes.append(env_node) #

            # Empty file
            if env_node.structure is None:
                continue

            # Save mappings
            if ('resource_registry' in env_node.structure) and (env_node.structure['resource_registry'] is not None):
                for origin, custom in six.iteritems(env_node.structure['resource_registry']):
                    if type(custom) == str:
                        env_node.resource_registry[origin] = custom
                    elif origin == 'resources':

                        # Find if there is any mapping (hooks etc are not important)
                        for res in env_node.structure['resource_registry']['resources'].keys():
                            for key, value in six.iteritems(
                                env_node.structure['resource_registry']['resources'][res]):

                                # Add indirect mapping using regexp - multiple indentations
                                if (type(value) == str) and (value.endswith('.yaml')):
                                    env_code.resource_registry[key] = [value, res]

            # Save additional parameters + parameters with default values
            if ('parameters' in env_node.structure) and (env_node.structure['parameters'] is not None):
                for par in list(env_node.structure['parameters'].keys()):
                    env_node.params[par] = False

            if ('parameter_defaults' in env_node.structure) and (env_node.structure['parameter_defaults'] is not None):
                for par in list(env_node.structure['parameter_defaults'].keys()):
                    env_node.params_default[par] = False

            # Create HOT files with mapped files
            for child in list(env_node.resource_registry.values()):
                if ((type(child) == str and child.endswith('.yaml')) or
                    ((type(child) == list) and child[0].endswith('.yaml'))):

                    # If a file is created already as a root, no need for redundancy
                    found = False
                    for m in self.mappings:
                        if ((m.path == child) and (m.parent in self.environments)):
                            env_node.children.append(m)
                            found = True
                            break

                    if not found:
                        env_node.children.append(hotfile.HotFile(env_node, child))
                        self.mappings.append(env_node.children[-1])

            # Remove from currently validated files
            self.curr_nodes.remove(env_node)


    def add_param_defaults(self):
        ''' Add default from param_defaults where missing '''
        for env in self.environments:
            for key, value in six.iteritems(env.params_default):
                found = False
                # Find corresponding parameter(s)
                for hot in self.templates + self.mappings:
                    for p in hot.params:
                        # Parameter found
                        if key == p.name:
                            found = True

                            # Set value if needed
                            if p.default is None:
                                p.default = value
                                break

                if not found:
                    env.invalid.append(hotclasses.InvalidReference(key,
                             '', enum.ErrorTypes.ENV_PARAM_DEFAULT, None))

    def add_parameters(self):
        ''' Add additional parameters from prompt to root template file
            Add parameter values from environments to root template file
        '''

        # Add parameters and values from prompt (-P)
        if self.parameters:
            for key, value in six.iteritems(self.parameters):

                # If parameter exists, only insert value
                found = False
                for p in self.templates[0].params:
                    if p.name == key:
                        p.value = value
                        found = True
                        break

                # If not, create one (TODO or error?)
                if not found:
                    self.templates[0].params.append(hotclasses.PropertyParameter((key, value), True))

        # Assign values to parameters from environments
        for env in self.environments:
            if env.params is not None:

                # Go through all parameters declare in environments
                for key, value in six.iteritems(env.params):
                    found = False
                    for p in self.templates[0].params:
                        if p.name == key:
                            p.value = value
                            found = True
                            break

                    # If parameter does not exist in the root template
                    if not found:
                        env.invalid.append(hotclasses.InvalidReference(key,
                             '', enum.ErrorTypes.ENV_PARAM, None))

    def find_mapping(self, mapping):
        ''' Searches if there is a mapping with passed side available.
            mapping - left side of mapping
            returns first found right side of the mapping if found or None
        '''

        for env in self.environments:
            for origin, mapped in six.iteritems(env.resource_registry):
                if origin == mapping:
                    return (mapped, env)
        return None

    #def map_2search(self, root):
        #''' Go through mappings, apply to templates using DFS'''
        #for env in self.environments:
            #for origin, mapped in six.iteritems(env.resource_registry):
                #for r in root.resources:
                    #self.map_2apply(r, origin, mapped)
    # TODO: go through the template tree, try to apply wildcard mapping
        #       and direct mapping after that, create clone mappings
        #       on the way

    def apply_mappings(self):
        ''' Add all files mapped to resources as children in parent node. '''

        # Try to find resources for every mapping in the resource registry
        for env in self.environments:
            for origin, mapped in six.iteritems(env.resource_registry):
                self.map_resources(origin, mapped, env)


    def map_resources(self, origin, mapped, env):
        ''' Finds applicable resources, changes their type.
            origin - original type
            mapped - mapped type
            env - environment file
        '''

        # Wildcard
        if '*' in origin:

            # Find all resources corresponding to the wildcard
            for hot in self.templates + self.mappings:
                for r in hot.resources:

                    # Change their type
                    if (origin.startswith('*') and r.type.endswith(origin[1:])):
                        r.type = r.type.replace(origin[1:], mapped[1:])
                        
                    elif (origin.endswith('*') and r.type.startswith(origin[:-1])):
                        r.type = r.type.replace(origin[:-1], mapped[:-1])

                    # Find out if newly mapped resources have other applicable mappings
                    ret = self.find_mapping(r.type)
                    if ret is not None:
                        # If yes, apply mappings (might be that this mapping
                        # has already been realized in apply_mappings)
                        self.map_resources(r.type, ret[0], ret[1]) 

        # Direct mapping
        else:

            found = False
            # Find all corresponding resources
            for hot in self.templates + self.mappings:
                for r in hot.resources:

                    if r.child is not None:
                        continue

                    # Finds mapped file if the mapping is designated for the resource
                    if ((r.type == origin) and
                        ((type(mapped) == str) or (mapped[1] == r.name))):

                        # Find mapped YAML file/other type, assign it to the resource
                        for m in self.mappings:

                            # Other nonYAML type
                            if (type(mapped) == str) and (not mapped.endswith('.yaml')):
                                r.type = mapped
                                found = True

                            # YAML mapping
                            # TODO: create mapping clones for mappings applied multiple times!
                            elif (((type(mapped) == str) and (m.path == mapped)) or
                                ((type(mapped) == list) and (m.path == mapped[0]))):
                                # If it is already mapped somewhere, create a clone
                                if m.parent != env:
                                    self.mappings.append(m.clone_file(r.hotfile))
                                    r.child = self.mappings[-1]
                                else:
                                    m.parent = r.hotfile
                                    r.child = m
                                r.type = mapped
                                found = True
                                break

            if found:
                ret = self.find_mapping(mapped)
                if ret is not None:
                    # If yes, apply mappings (might be that this mapping
                    # has already been realized in apply_mappings)
                    self.map_resources(mapped, ret[0], ret[1]) 


    def validate_env_params(self):
        ''' Checks parameters section of environment files. '''

        # Check parameters section
        for env in self.environments:
            for par in list(env.params.keys()):
                if par in [p.name for p in self.templates[0].params]:
                    env.params[par] = True
                    break

        # Check parameter_defaults section
        for env in self.environments:
            for par in list(env.params_default.keys()):
                for hot in self.templates + self.mappings:
                    if par in [x.name for x in hot.params]:
                        env.params_default[par] = True
                        break


    def validate_properties(self, template):
        ''' Validate properties x parameters in tree of templates. '''

        # Add current node at the beginning
        self.curr_nodes.append(self)

        # Go through all resources in current template
        for resource in template.resources:

            # Continue with child nodes
            if resource.child is not None:
                resource.child.check_prop_par(template, resource,
                                              self.environments)
                self.validate_properties(resource.child)

        # Remove node from current nodes after validation
        self.curr_nodes.remove(self)


    def validate_references(self, root):
        ''' Validates references in file '''

        # Validate parent
        root.validate_file(self.curr_nodes)

        # Go through all resources in current template
        for resource in root.resources:

            # Continue with child nodes
            if resource.child is not None:
                self.validate_references(resource.child)

    def print_tree(self, root, root_position, indent, branch_list):
        ''' Prints tree structure of templates '''

        # Print higher branches
        if (len(branch_list) and (root_position != enum.TreeInfo.ONLY)):
            cur_indent = 0
            print('')
            for i in branch_list:
                print ((i-cur_indent-1) * '   ' + '│   ', end="")
                cur_indent = i
            print ((indent-cur_indent-1) * '   ', end="")
        elif root_position != enum.TreeInfo.ONLY:
            print ('\n' + (indent-1) * '   ', end="")

        # Print child node
        if indent > 0:
            if root_position == enum.TreeInfo.ONLY:
                print (' ── ' + root.path, end="")
            elif root_position == enum.TreeInfo.OTHER:
                print ('├─ ' + root.path, end="")
            elif root_position == enum.TreeInfo.LAST:
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

        # Determine child position
        if ((lastindex is not None) and (lastindex == firstindex)):
            child_position = enum.TreeInfo.ONLY
        else:
            child_position = enum.TreeInfo.OTHER

        # Add branch to indicate another |
        if root_position != enum.TreeInfo.ONLY:
            branch_list = branch_list + [indent-1]

        # Print subtrees of children
        for r in root.resources:
            if r.child is not None:
                if ((child_position != enum.TreeInfo.ONLY) and
                    (root.resources.index(r) == lastindex)):
                    child_position = enum.TreeInfo.LAST

                self.print_tree(r.child, child_position, indent, branch_list)


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
        for hot in self.mappings:
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

        # Add param_defaults from environments where default is missing
        self.add_param_defaults()
        self.add_parameters()

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Also add mapped files as children once there is a full structure of files
        # (if done earlier, some mapped types used in mapped files could be skipped)
        self.apply_mappings()

        # Check environment parameters against fully loaded HOT structure
        self.validate_env_params()

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Check properties x parameters
        self.validate_properties(self.templates[0])

        for hot in self.mappings:
            if hot.parent in self.environments:
                self.validate_properties(hot)

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)

        # Validate references
        self.validate_references(self.templates[0])

        if self.print_nyan:
            progress.task_done()
            time.sleep(self.sleep_time)
            progress.finish()


    def print_output(self):
        ''' Prints results of validation for all files + additional info. '''

        # Environments
        if self.environments:
            if self.pretty_format:
                print(enum.Fonts.ORANGE + enum.Fonts.BOLD + enum.Fonts.UNDERLINE +
                      'Environments:' + enum.Fonts.DEFAULT)
            else:
                print('Environments:')

            # Print total
            if self.pretty_format:
                print(enum.Fonts.BOLD + 'Total: ' + str(len(self.environments)) +
                      enum.Fonts.DEFAULT)
            else:
                print ('Total: ' + str(len(self.environments)))
            print('')

            for env in self.environments:

                # Print title
                if self.pretty_format:
                    print(enum.Fonts.BOLD + enum.Fonts.UNDERLINE +
                          'File ' + enum.Fonts.BLUE +
                          os.path.relpath(env.path, self.init_dir) +
                          enum.Fonts.DEFAULT)
                else:
                    print('File ' + os.path.relpath(env.path, self.init_dir))
                print('')

                # Parameters section
                if env.invalid:
                    env.ok = False

                    for ref in env.invalid:
                        if ref.type == enum.ErrorTypes.ENV_PARAM:
                            if self.pretty_format:
                                print ('Parameter ' + enum.Fonts.YELLOW +
                                       ref.referent + enum.Fonts.DEFAULT +
                                       ' has no match in root template.')
                            else:
                                print ('Parameter ' + ref.referent + ' has no match in root template.')

                        # Parameter_defaults section
                        elif ref.type == enum.ErrorTypes.ENV_PARAM_DEFAULT:
                            if self.pretty_format:
                                print ('Parameter default ' + enum.Fonts.YELLOW +
                                       ref.referent + enum.Fonts.DEFAULT +
                                       ' has no match in the stack.')
                            else:
                                print ('Parameter default' + ref.referent + ' has no match in the stack.')
                    print('')

                # Print file status as OK if there were no problems
                if env.ok:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD + 'Status: ' + enum.Fonts.GREEN +
                              'OK' + enum.Fonts.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD + 'Status: ' + enum.Fonts.RED +
                              'FAILED' + enum.Fonts.DEFAULT)
                    else:
                        print('Status: FAILED')

                print('\n\n')

        # HOT Files and mappings
        # TODO: Print as DFS, rather going through the tree instead of the list
        for hot in [x for x in [self.templates, self.mappings] if len(x)]:
            
            if self.pretty_format:
                print(enum.Fonts.ORANGE + enum.Fonts.BOLD + enum.Fonts.UNDERLINE +
                      ('HOT Files:' if hot == self.templates else 'Mapped HOT Files:') +
                      enum.Fonts.DEFAULT)
            else:
                print(('HOT Files:' if hot == self.templates else 'Mapped HOT Files:'))

            # Print total
            if self.pretty_format:
                print(enum.Fonts.BOLD + 'Total: ' + str(len(self.templates) if hot == self.templates else len(self.mappings)) +
                      enum.Fonts.DEFAULT)
            else:
                print ('Total: ' + str(len(self.templates) if hot == self.templates else len(self.mappings)))
            print('')

            for node in hot:

                if node != hot[0]:
                    print('\n')

                # Print title
                if self.pretty_format:
                    print(enum.Fonts.BOLD + enum.Fonts.UNDERLINE + 'File ' +
                          enum.Fonts.BLUE + os.path.relpath(node.path, self.init_dir) + 
                          enum.Fonts.DEFAULT)
                else:
                    print('File ' + os.path.relpath(node.path, self.init_dir))

                # Print parent node for better navigation
                if self.pretty_format:
                    print(enum.Fonts.BOLD + 'Parent: ' + enum.Fonts.DEFAULT +
                          (os.path.relpath(node.parent.path, self.init_dir) if (node.parent is not None) else 'None (root)'))
                else:
                    print('Parent: ' + (os.path.relpath(node.parent.path,
                          self.init_dir) if (node.parent is not None) else 'None (root)'))
                print('')

                # Invalid references
                # TODO: optimize so that no error has two invalid records (esp. in case of nested)
                if node.invalid:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD + 'Invalid references:' + enum.Fonts.DEFAULT)
                    else:
                        print('Invalid references:')

                    for ref in node.invalid:
                        # get_resource
                        if ref.type == enum.ErrorTypes.GET_RESOURCE:
                            if self.pretty_format:
                                print ('Resource ' + enum.Fonts.YELLOW + ref.referent +
                                       enum.Fonts.DEFAULT + ' referred in ' + enum.Fonts.YELLOW +
                                       ref.element + enum.Fonts.DEFAULT + ' is not declared.')
                            else:
                                print ('Resource ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        # get_param
                        elif ref.type == enum.ErrorTypes.GET_PARAM:
                            if self.pretty_format:
                                print ('Parameter ' + enum.Fonts.YELLOW + ref.referent +
                                       enum.Fonts.DEFAULT + ' referred in ' + enum.Fonts.YELLOW +
                                       ref.element + enum.Fonts.DEFAULT + ' is not declared.')
                            else:
                                print ('Parameter ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        # get_attr
                        elif ref.type == enum.ErrorTypes.GET_ATTR:
                            if self.pretty_format:
                                print ('Instance ' + enum.Fonts.YELLOW + ref.referent +
                                       enum.Fonts.DEFAULT + ' referred by ' + enum.Fonts.YELLOW +
                                       'get_attr' + enum.Fonts.DEFAULT + ' in ' + enum.Fonts.YELLOW +
                                       ref.element + enum.Fonts.DEFAULT + ' is not declared.')
                            else:
                                print ('Instance ' + ref.referent + ' referred by get_attr in ' +
                                       ref.element + ' is not declared.')

                        # missing property
                        elif ref.type == enum.ErrorTypes.MISS_PROP:
                            if self.pretty_format:
                                print('Parameter ' + enum.Fonts.YELLOW + ref.referent + enum.Fonts.DEFAULT +
                                      ' has no corresponding default or property in ' +  enum.Fonts.YELLOW +
                                      ref.element + enum.Fonts.DEFAULT + ' in ' +
                                      enum.Fonts.YELLOW + os.path.relpath(ref.parent, self.init_dir) + enum.Fonts.DEFAULT + '.')
                            else:
                                print('Parameter ' + ref.referent + ' has no corresponding default or property in ' +
                                      ref.element + ' in ' + os.path.relpath(ref.parent, self.init_dir) + '.')

                        # missing parameter
                        elif ref.type == enum.ErrorTypes.MISS_PARAM:
                            if self.pretty_format:
                                print('Property ' + enum.Fonts.YELLOW + ref.referent + enum.Fonts.DEFAULT +
                                      ' has no corresponding parameter in ' + enum.Fonts.YELLOW +
                                      os.path.relpath(ref.parent, self.init_dir) + enum.Fonts.DEFAULT + '.')
                            else:
                                print('Property ' + ref.referent + ' has no corresponding parameter in ' +
                                      os.path.relpath(ref.parent, self.init_dir) + '.')

                        # dependency not found
                        elif ref.type == enum.ErrorTypes.DEPENDS_ON:
                            if self.pretty_format:
                                print('Resource ' + enum.Fonts.YELLOW + ref.referent + enum.Fonts.DEFAULT +
                                      ' that resource ' +  enum.Fonts.YELLOW +
                                      ref.element + enum.Fonts.DEFAULT + ' depends on is not declared.')
                            else:
                                print('Resource ' + ref.referent + ' that resource ' +
                                      ref.element + ' depends on is not declared.')
                    print('')

                # Unused parameters
                if False in [x.used for x in node.params]:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD +  'Unused parameters:' + enum.Fonts.DEFAULT)
                    else:
                        print('Unused parameters:')

                    for par in node.params:
                        if par.used == False:
                            if self.pretty_format:
                                print('- ' + enum.Fonts.YELLOW + par.name + enum.Fonts.DEFAULT)
                            else:
                                print('- ' + par.name)
                    print('')

                # Print hidden parameters (optional)
                if (self.print_unused) and [True for x in node.params if x.hidden]:
                    if (self.pretty_format):
                        print(enum.Fonts.BOLD + 'Hidden parameters:' +
                              enum.Fonts.DEFAULT)
                    else:
                        print('Hidden parameters:')
                    
                    for par in node.params:
                        if par.hidden:
                            if self.pretty_format:
                                print('- ' + enum.Fonts.YELLOW + par.name + enum.Fonts.DEFAULT)
                            else:
                                print('- ' + par.name)
                    print('')
                
                # Print unused resources (optional)
                if (self.print_unused) and [True for x in node.resources if not x.used]:
                    if (self.pretty_format):
                        print(enum.Fonts.BOLD + 'Resources without reference:' +
                              enum.Fonts.DEFAULT)
                    else:
                        print('Resources without reference:')

                    for resource in node.resources:
                        if resource.used == False:
                            if self.pretty_format:
                                print('- ' + enum.Fonts.YELLOW + resource.name + enum.Fonts.DEFAULT +
                                      ' (' + resource.type + ')')
                            else:
                                print('- ' + resource.name)
                    print('')

                # Print file status as OK if there were no problems
                if node.ok:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD + 'Status: ' + enum.Fonts.GREEN +
                              'OK' + enum.Fonts.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(enum.Fonts.BOLD + 'Status: ' + enum.Fonts.RED +
                              'FAILED' + enum.Fonts.DEFAULT)
                    else:
                        print('Status: FAILED')

        # Print tree structure
        if self.print_structure:
            if self.pretty_format:
                print(enum.Fonts.ORANGE + enum.Fonts.BOLD + enum.Fonts.UNDERLINE +
                      'Structure:' + enum.Fonts.DEFAULT)
            else:
                print('Structure:')

            self.print_tree(self.templates[-1], enum.TreeInfo.ONLY, 0, [])
            print('\n')
