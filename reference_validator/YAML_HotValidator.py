#!/usr/bin/env python
#coding=utf-8

# File: YAML_HotValidator.py
# Brief: Contains class YAML_HotValidator for validating references
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import os
import pprint
import sys
import six  # compatibility
import yaml # pip install pyyaml

import YAML_Enums as ENUM
import YAML_Hotfile as HOT
import YAML_HotClasses

# only for Python 2.x
if sys.version_info[0] == 2:
    import nyanbar

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
            self.templates.insert(0, HOT.YAML_Hotfile(None, abs_path))
        else:
            print('Wrong template file suffix (YAML expected).')
            sys.exit(1)

        # Check environment files (-e)
        if arguments['environment']:
            for env in list(arguments['environment']):
                abs_path = os.path.abspath(env)
                if abs_path.endswith('yaml'):
                    self.environments.insert(0, YAML_HotClasses.YAML_Env(None, abs_path))


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
                        env_node.children.insert(0, HOT.YAML_Hotfile(env_node, child))
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
                                    m.parent = res.hotfile
                                    #print (res.type + ' type is mapped to file ' + res.child.path)
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
        if (len(branch_list) and (root_position != ENUM.YAML_tree_info.ONLY)):
            cur_indent = 0
            print('')
            for i in branch_list:
                print ((i-cur_indent-1) * '   ' + '│   ', end="")
                cur_indent = i
            print ((indent-cur_indent-1) * '   ', end="")
        elif root_position != ENUM.YAML_tree_info.ONLY:
            print ('\n' + (indent-1) * '   ', end="")
                
        # Print child node
        if indent > 0:
            if root_position == ENUM.YAML_tree_info.ONLY:
                print (' ── ' + root.path, end="")
            elif root_position == ENUM.YAML_tree_info.OTHER:
                print ('├─ ' + root.path, end="")
            elif root_position == ENUM.YAML_tree_info.LAST:
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

        child_position = (ENUM.YAML_tree_info.ONLY if ((lastindex is not None) and (lastindex == firstindex)) else ENUM.YAML_tree_info.OTHER)
        branch_list = branch_list + ([indent-1] if root_position != ENUM.YAML_tree_info.ONLY else [])

        # Print subtrees of children
        for r in root.resources:
            if r.child is not None:
                if ((child_position != ENUM.YAML_tree_info.ONLY) and (root.resources.index(r) == lastindex)):
                    child_position = ENUM.YAML_tree_info.LAST

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


    def print_output(self):
        ''' Prints results of validation for all files + additional info. '''

        # Environments
        if self.environments:
            if self.pretty_format:
                print(ENUM.YAML_colours.ORANGE + ENUM.YAML_colours.BOLD + ENUM.YAML_colours.UNDERLINE +
                      'Environments:' + ENUM.YAML_colours.DEFAULT)
            else:
                print('Environments:')

            # Print total
            if self.pretty_format:
                print(ENUM.YAML_colours.BOLD + 'Total: ' + str(len(self.environments)) +
                      ENUM.YAML_colours.DEFAULT)
            else:
                print ('Total: ' + str(len(self.environments)))
            print('')

            for env in self.environments:

                # Print title
                if self.pretty_format:
                    print(ENUM.YAML_colours.BOLD + ENUM.YAML_colours.UNDERLINE +
                          'File ' + ENUM.YAML_colours.BLUE +
                          os.path.relpath(env.path, self.init_dir) +
                          ENUM.YAML_colours.DEFAULT)
                else:
                    print('File ' + os.path.relpath(env.path, self.init_dir))
                print('')

                # Parameters section
                if False in list(env.params.values()):
                    env.ok = False
                    if self.pretty_format:
                         print (ENUM.YAML_colours.BOLD + 'Parameters without match in root template:' +
                                ENUM.YAML_colours.DEFAULT)
                    else:
                         print ('Parameters without match in root template:')
                    for par in [x for x in list(env.params.keys())
                                if env.params[x] == False]:
                        if self.pretty_format:
                            print ('- ' + ENUM.YAML_colours.YELLOW + par + ENUM.YAML_colours.DEFAULT)
                        else:
                            print ('- ' + par)
                    print('')

                # Parameter_defaults section (optional)
                if self.print_unused and (False in list(env.params_default.values())):
                    if self.pretty_format:
                        print (ENUM.YAML_colours.BOLD + 'Parameter defaults without match:' +
                               ENUM.YAML_colours.DEFAULT)
                    else:
                        print ('Parameter defaults without match:')

                    for par in [x for x in list(env.params_default.keys())
                                if env.params_default[x] == False]:
                        if self.pretty_format:
                            print ('- ' + ENUM.YAML_colours.YELLOW + par +
                                    ENUM.YAML_colours.DEFAULT)
                        else:
                            print ('- ' + par)
                    print('')

                # Print file status as OK if there were no problems
                if env.ok:
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD + 'Status: ' + ENUM.YAML_colours.GREEN +
                              'OK' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD + 'Status: ' + ENUM.YAML_colours.RED +
                              'FAILED' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print('Status: FAILED')

                print('\n\n')


        # HOT Files and mappings
        rev_templates = list(reversed(self.templates))
        for hot in [x for x in [rev_templates, list(reversed(self.mappings))] if len(x)]:
            if self.pretty_format:
                print(ENUM.YAML_colours.ORANGE + ENUM.YAML_colours.BOLD + ENUM.YAML_colours.UNDERLINE +
                      ('HOT Files:' if hot == rev_templates else 'Mapped HOT Files:') +
                      ENUM.YAML_colours.DEFAULT)
            else:
                print(('HOT Files:' if hot == rev_templates else 'Mapped HOT Files:'))

            # Print total
            if self.pretty_format:
                print(ENUM.YAML_colours.BOLD + 'Total: ' + str(len(self.templates) if hot == rev_templates else len(self.mappings)) +
                      ENUM.YAML_colours.DEFAULT)
            else:
                print ('Total: ' + str(len(self.templates) if hot == rev_templates else len(self.mappings)))
            print('')

            for node in hot:

                # Print title
                if self.pretty_format:
                    print(ENUM.YAML_colours.BOLD + ENUM.YAML_colours.UNDERLINE + 'File ' +
                          ENUM.YAML_colours.BLUE + node.path + ENUM.YAML_colours.DEFAULT)
                else:
                    print('File ' + node.path)

                # Print parent node for better navigation
                if self.pretty_format:
                    print(ENUM.YAML_colours.BOLD + 'Parent: ' + ENUM.YAML_colours.DEFAULT +
                          (os.path.relpath(node.parent.path, self.init_dir) if (node.parent is not None) else 'None (root)'))
                else:
                    print('Parent: ' + (os.path.relpath(node.parent.path, self.init_dir) if (node.parent is not None) else 'None (root)'))
                print('')

                # Print children nodes
                #if [True for x in node.resources if x.child is not None]:
                #    if self.pretty_format:
                #        print(ENUM.YAML_colours.BOLD + 'Children:' + ENUM.YAML_colours.DEFAULT)
                #    else:
                #        print('Children:')

                #    for res in node.resources:
                #        if res.child is not None:
                #            print('- ' + res.child.path)
                #    print('')

                # Invalid references
                if node.invalid:
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD + 'Invalid references:' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print('Invalid references:')

                    for ref in node.invalid:
                        # get_resource
                        if ref.type == ENUM.YAML_Types.GET_RESOURCE:
                            if self.pretty_format:
                                print ('Resource ' + ENUM.YAML_colours.YELLOW + ref.referent +
                                       ENUM.YAML_colours.DEFAULT + ' referred in ' + ENUM.YAML_colours.YELLOW +
                                       ref.element + ENUM.YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Resource ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        # get_param
                        elif ref.type == ENUM.YAML_Types.GET_PARAM:
                            if self.pretty_format:
                                print ('Parameter ' + ENUM.YAML_colours.YELLOW + ref.referent +
                                       ENUM.YAML_colours.DEFAULT + ' referred in ' + ENUM.YAML_colours.YELLOW +
                                       ref.element + ENUM.YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Parameter ' + ref.referent + ' referred in ' + ref.element +
                                       ' is not declared.')

                        # get_attr
                        elif ref.type == ENUM.YAML_Types.GET_ATTR:
                            if self.pretty_format:
                                print ('Instance ' + ENUM.YAML_colours.YELLOW + ref.referent +
                                       ENUM.YAML_colours.DEFAULT + ' referred by ' + ENUM.YAML_colours.YELLOW +
                                       'get_attr' + ENUM.YAML_colours.DEFAULT + ' in ' + ENUM.YAML_colours.YELLOW +
                                       ref.element + ENUM.YAML_colours.DEFAULT + ' is not declared.')
                            else:
                                print ('Instance ' + ref.referent + ' referred by get_attr in ' +
                                       ref.element + ' is not declared.')

                        # missing property
                        elif ref.type == ENUM.YAML_Types.MISS_PROP:
                            if self.pretty_format:
                                print('Parameter ' + ENUM.YAML_colours.YELLOW + ref.referent + ENUM.YAML_colours.DEFAULT +
                                      ' has no corresponding default or property in ' +  ENUM.YAML_colours.YELLOW +
                                      ref.element + ENUM.YAML_colours.DEFAULT + ' in ' +
                                      ENUM.YAML_colours.YELLOW + os.path.relpath(ref.parent, self.init_dir) + ENUM.YAML_colours.DEFAULT + '.')
                            else:
                                print('Parameter ' + ref.referent + ' has no corresponding default or property in ' +
                                      ref.element + ' in ' + os.path.relpath(ref.parent, self.init_dir) + '.')

                        # missing parameter
                        elif ref.type == ENUM.YAML_Types.MISS_PARAM:
                            if self.pretty_format:
                                print('Property ' + ENUM.YAML_colours.YELLOW + ref.referent + ENUM.YAML_colours.DEFAULT +
                                      ' has no corresponding parameter in ' + ENUM.YAML_colours.YELLOW +
                                      os.path.relpath(ref.parent, self.init_dir) + ENUM.YAML_colours.DEFAULT + '.')
                            else:
                                print('Property ' + ref.referent + ' has no corresponding parameter in ' +
                                      os.path.relpath(ref.parent, self.init_dir) + '.')

                        # dependency not found
                        elif ref.type == ENUM.YAML_Types.DEPENDS_ON:
                            if self.pretty_format:
                                print('Resource ' + ENUM.YAML_colours.YELLOW + ref.referent + ENUM.YAML_colours.DEFAULT +
                                      ' that resource ' +  ENUM.YAML_colours.YELLOW +
                                      ref.element + ENUM.YAML_colours.DEFAULT + ' depends on is not declared.')
                            else:
                                print('Resource ' + ref.referent + ' that resource ' +
                                      ref.element + ' depends on is not declared.')
                    print('')

                # Unused parameters (optional) ??
                if self.print_unused and (False in [x.used for x in node.params]):
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD +  'Unused parameters:' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print('Unused parameters:')

                    for par in node.params:
                        if par.used == False:
                            if self.pretty_format:
                                print('- ' + ENUM.YAML_colours.YELLOW + par.name + ENUM.YAML_colours.DEFAULT)
                            else:
                                print('- ' + par.name)
                    print('')

                # Print unused resources (optional)
                if (self.print_unused) and [True for x in node.resources if not x.used]:
                    if (self.pretty_format):
                        print(ENUM.YAML_colours.BOLD + 'Resources without reference:' +
                              ENUM.YAML_colours.DEFAULT)
                    else:
                        print('Resources without reference:')

                    for resource in node.resources:
                        if resource.used == False:
                            if self.pretty_format:
                                print('- ' + ENUM.YAML_colours.YELLOW + resource.name + ENUM.YAML_colours.DEFAULT +
                                      ' (' + resource.type + ')')
                            else:
                                print('- ' + resource.name)
                    print('')

                # Print file status as OK if there were no problems
                if node.ok:
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD + 'Status: ' + ENUM.YAML_colours.GREEN +
                              'OK' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print ('Status: OK')
                else:
                    if self.pretty_format:
                        print(ENUM.YAML_colours.BOLD + 'Status: ' + ENUM.YAML_colours.RED +
                              'FAILED' + ENUM.YAML_colours.DEFAULT)
                    else:
                        print('Status: FAILED')

                print('\n')

        if self.print_structure:
            if self.pretty_format:
                print(ENUM.YAML_colours.ORANGE + ENUM.YAML_colours.BOLD + ENUM.YAML_colours.UNDERLINE +
                      'Structure:' + ENUM.YAML_colours.DEFAULT)
            else:
                print('Structure:')

            self.print_tree(self.templates[-1], ENUM.YAML_tree_info.ONLY, 0, [])
            print('\n')
