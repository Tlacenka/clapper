#!/usr/bin/env python
#coding=utf-8

# File: hotfile.py
# Brief: Class HotFile for validating HOT files
# Author: Katerina Pilatova (kpilatov)
# Date: 2016
# - TODO: remove duplicate error messages when there is an error in get_ with nested structure


from __future__ import with_statement, print_function

import os
import sys
import six  # compatibility
import yaml # pip install pyyaml

import enum
import hotclasses


class HotFile:
    ''' Class with attributes needed for work with HOT files. '''

    def __init__(self, parent_node, abs_path):
        ''' Node is initiated when being detected. '''

        self.path = abs_path

        self.parent = parent_node   # Parent node or nothing in the case of root node

        self.resources = []         # Resource list
        self.params = []            # list of PropertyParameter
                                    # TODO exception for root template when checking properties values

        self.outputs = {}           # {name : <value structure>}

        self.structure = {}         # structure of YAML file
        self.ok = True

        self.invalid = []           # list of invalid references (Reference)


    def clone_file(self, new_parent):
        ''' Clone file, optionally adds new parent straight away,
            mutable objects such as structure are shared.
        '''
        new_file = HotFile(new_parent, self.path)

        # create new instances of property/parameter objects
        for r in self.resources:
            new_file.resources.append(r.clone())

        for p in self.params:
            new_file.params.append(p.clone())

        new_file.outputs = self.outputs # outputs section remains
        new_file.structure = self.structure # the file structure remains
        # ok and invalid do not need to be changed

        return new_file

    def load_file(self, curr_nodes, templates, environments, curr_path):
        ''' Validate YAML file. '''

        # Add current node at the beginning
        curr_nodes.append(self)

        # Open file
        try:
            with open(os.path.join(curr_path, self.path), 'r') as fd:
                self.structure = yaml.load(fd.read())
        except IOError:
            print('File ' + self.path + ' could not be opened.', file=sys.stderr)
            sys.exit(1)
        except Exception as err:
            print('ERROR invalid YAML format in file ' + self.path +
                  ': ' + str(err), file=sys.stderr)
            sys.exit(1)

        # Empty file
        if self.structure is None:
            return

        # Save all parameters names, resources and properties
        if ('parameters' in self.structure) and (self.structure['parameters'] is not None):
            for param in self.structure['parameters'].items():
                self.params.append(hotclasses.PropertyParameter(param, True))

        if ('resources' in self.structure) and (self.structure['resources'] is not None):
            for key, value in six.iteritems(self.structure['resources']):
                self.resources.append(hotclasses.Resource(key, value, self))

        if ('outputs' in self.structure) and (self.structure['outputs'] is not None):
            for key, value in six.iteritems(self.structure['outputs']):
                self.outputs[key] = value

        # Examine children nodes to get the full information about references
        for resource in self.resources:
            if (resource.type is not None) and (resource.type.endswith('.yaml')):
                templates.append(HotFile(self, resource.type))

                # Add child
                resource.child = templates[-1]

                # Start validating child
                templates[-1].load_file(curr_nodes, templates, environments,
                                       os.path.join(curr_path, os.path.dirname(self.path)))

                # The whole subtree with root = current node is loaded

        # Remove node from current nodes after loading
        curr_nodes.remove(self)


    def validate_file(self, curr_nodes):
        ''' After loading information, validate references in file. '''

        # Add current node at the beginning
        curr_nodes.append(self)

        # If the file is empty
        if self.structure is None:
            return

        # Iterate over sections (all children validated by now)
        for section, instances in six.iteritems(self.structure):
            # skip those without nested structures
            if type(instances) == dict:

                # Iterate over instances (variables)
                for key, value in six.iteritems(instances):
                    self.validate_instances(key, value)

        # Check dependencies
        self.depends_on()

        # Remove node from current nodes after validation
        curr_nodes.remove(self)


    def validate_instances(self, name, structure):
        ''' Check if all references to variables are valid.
            name       - name of referring instance
            structure - structure containing instance properties and their values

        '''

        if isinstance(structure, list):
            for s in structure:
                if isinstance(s, dict) or isinstance(s, list):
                    self.validate_instances(name, s)

        elif isinstance(structure, dict):
            # Classify references
            for key, value in six.iteritems(structure):
                if self.classify_items(key, value, name) is None:
                    self.validate_instances(name, value)


    def classify_items(self, key, value, name):
       ''' If item contains reference, it is processed. '''

       if key == 'get_param':
           return self.get_param(value, name)
       elif key == 'get_resource':
           return self.get_resource(value, name)
       elif key == 'get_attr':
           return self.get_attr(value, name)
       else:
           return None


    def get_param(self, hierarchy, name):
        ''' Validate get_param.
            hierarchy - reference
            name - instance name
        '''

        # main variables: cur_state, next_state
        cur_state = enum.GetParamStates.INIT
        next_state = enum.GetParamStates.INIT

        parameter = None # referenced parameter
        value = None     # searched value

        element = None   # value of current element (string)
        index = 0        # index of current element

        while True:

            # State transition
            cur_state = next_state

            # Initiate resolution
            if cur_state == enum.GetParamStates.INIT:
                if ((type(hierarchy) == str) or
                    ((type(hierarchy) == list) and (len(hierarchy) > 0))):
                    next_state = enum.GetParamStates.PARAM_NAME
                else:
                    next_state = enum.GetParamStates.ERROR

            # End unsuccessfully
            elif cur_state == enum.GetParamStates.ERROR:
                if type(hierarchy) == list:
                    self.invalid.append(hotclasses.InvalidReference(str(hierarchy[index]),
                                name, enum.ErrorTypes.GET_PARAM, None))
                else:
                    self.invalid.append(hotclasses.InvalidReference(str(hierarchy),
                                name, enum.ErrorTypes.GET_PARAM, None))
                self.ok = False
                return None

            # End successfully
            elif cur_state == enum.GetParamStates.RESOLVED:
                if parameter is not None:
                    parameter.used = True
                return (value if (value is not None) else element)

            # Find parameter
            elif cur_state == enum.GetParamStates.PARAM_NAME:
                if type(hierarchy) == str:
                    # Resolve pseudo parameters
                    if hierarchy in ('OS::stack_name', 'OS::stack_id', 'OS::project_id'):
                        next_state = enum.GetParamStates.RESOLVED
                        continue
                    else:
                        element = hierarchy

                elif type(hierarchy[index]) == dict:
                    element = self.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetParamStates.ERROR
                    continue

                elif type(element) == str:
                    for p in self.params:
                        if p.name == element:
                            parameter = p
                            break

                if parameter is None:
                    # Parameter was not found
                    next_state = enum.GetParamStates.ERROR
                else:
                    # Go to parameter value resolution
                    next_state = enum.GetParamStates.PARAM_VALUE

            # Find its value based on property/parameter value/default
            elif cur_state == enum.GetParamStates.PARAM_VALUE:

                # Try finding direct value
                tmp = None

                # If property has a get_ value and has a parent
                if ((type(parameter.value) == dict) and (len(parameter.value) == 1) and
                    ('get_' in list(parameter.value.keys())[0])):
                    if isinstance(self.parent, HotFile):
                        tmp = self.parent.resolve_nested(parameter.value, name)
                    else:
                        # parent is not a yaml file > cannot be traced
                        next_state = enum.GetParamStates.RESOLVED
                        continue
                else:
                    tmp = parameter.value

                value = tmp

                # Check parameter default if the value is not found
                if value is None:
                    if parameter.default is not None:
                        value = parameter.default
                    elif parameter.hidden:
                        # Ignore hidden for now...TODO
                        next_state = enum.GetParamStates.RESOLVED
                        continue
                    else:
                        next_state = enum.GetParamStates.ERROR
                        continue

                if type(hierarchy) == str:
                    # Parameter found, no hierarchy remaining
                    next_state = enum.GetParamStates.RESOLVED
                else:
                    next_state = enum.GetParamStates.PARAM_RESOLUTION
                    index = index + 1

            # Resolve searched value based on hierarchy
            elif cur_state == enum.GetParamStates.PARAM_RESOLUTION:

                # End of hierarchy
                if index >= len(hierarchy):
                    next_state = enum.GetParamStates.RESOLVED
                    continue

                # Resolve nested element
                if type(hierarchy[index]) == dict:
                    # TODO: can there be a get_ in default?
                    element = self.parent.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetParamStates.ERROR

                elif ((type(element) == str) and (type(value) == dict) and
                      (element in value.keys())):
                    value = value[element]
                    index = index + 1

                # Value is n-th element in list
                elif ((type(element) == int) and (type(value) == list) and
                      (element < len(value))):
                    # TODO will it be parsed by YAML parser as int or str?
                    value = value[element]
                    index = index + 1

                else:
                    # element can only be string or digit
                    next_state = enum.GetParamStates.ERROR


    def get_resource(self, hierarchy, name):
        ''' Validate get_resource.
            hierarchy - reference
            name - instance name
        '''

        for r in self.resources:
            if hierarchy == r.name:
                r.used = True
                return r

        # If not found, add it to invalid references
        self.invalid.append(hotclasses.InvalidReference(hierarchy, name,
                            enum.ErrorTypes.GET_RESOURCE, None))
        self.ok = False
        return None


    def get_attr(self, hierarchy, name):
        ''' Validate get_attr.
            hierarchy - reference
            name - instance name
        '''

        # main variables: cur_state, next_state, value
        cur_state = enum.GetAttrStates.INIT
        next_state = enum.GetAttrStates.INIT

        resource = None # Referenced resource
        value = None # Searched value

        element = None # Value of current element (string)
        index = 0 # Index of current element

        while True:

            # State transition
            cur_state = next_state

            # Initiate resolution
            if cur_state == enum.GetAttrStates.INIT:
                if (type(hierarchy) == list) and (len(hierarchy) > 1):
                    next_state = enum.GetAttrStates.RESOURCE_NAME
                else:
                    next_state = enum.GetAttrStates.ERROR

            # End unsuccessfully, add invalid reference
            elif cur_state == enum.GetAttrStates.ERROR:

                if (type(hierarchy) == list) and (len(hierarchy) > 0):
                    self.invalid.append(hotclasses.InvalidReference(str(hierarchy[index]),
                                name + ' - output of ' + str(hierarchy[0]),
                                enum.ErrorTypes.GET_ATTR, None))
                else:
                    self.invalid.append(hotclasses.InvalidReference(hierarchy,
                                name + ' - output of ' + str(hierarchy),
                                enum.ErrorTypes.GET_ATTR, None))

                self.ok = False
                return None

            # End successfully
            elif cur_state == enum.GetAttrStates.RESOLVED:
                resource.used = True
                return value

            # Resolve first element and its value, choose next state
            elif cur_state == enum.GetAttrStates.RESOURCE_NAME:
                # Resolve nested element
                if type(hierarchy[index]) == dict:
                    element = self.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetAttrStates.ERROR

                elif type(element) == str:
                    for r in self.resources:
                        if r.name == element:
                            resource = value = r
                            break

                    # Resource not found
                    if resource is None:
                        next_state = enum.GetAttrStates.ERROR

                    # Resource does not have a dedicated YAML file
                    elif resource.child is None:
                        next_state = enum.GetAttrStates.RESOLVED

                    # Based on next element, choose next state
                    else:
                        index = index + 1
                        if index >= len(hierarchy):
                            # No more elements found - TODO: is it invalid?
                            next_state = enum.GetAttrStates.ERROR
                            continue

                        if type(hierarchy[index]) == dict:
                            element = self.resolve_nested(hierarchy[index], name)
                        else:
                            element = hierarchy[index]

                        if element is None:
                            next_state = enum.GetAttrStates.ERROR
                        elif type(element) == str:
                            # 'attributes'
                            if ((resource.grouptype == enum.Grouptypes.RG) and
                                (element == 'attributes')):
                                index = index + 1
                                next_state = enum.GetAttrStates.RG_ATTRIBUTES

                            # 'outputs_list'
                            elif ((resource.grouptype == enum.Grouptypes.ASG) and
                                  (element == 'outputs_list')):
                                index = index + 1
                                next_state = enum.GetAttrStates.ASG_OUTPUTS_LIST
                            # 'outputs'
                            elif ((resource.grouptype == enum.Grouptypes.ASG) and
                                  (element == 'outputs')):
                                index = index + 1
                                next_state = enum.GetAttrStates.ASG_OUTPUTS
                            # 'resource.<name>', 'resource.<number>'
                            # 'resource.<number>.<name>' (RG), 'resource.<alphanum string>.<name>' (ASG)
                            elif element.startswith('resource.'):
                                tmp = element.split('.')

                                # resource.<number>.<ref> or resource.<number>
                                if ((resource.grouptype == enum.Grouptypes.RG) and
                                    ((len(tmp) == 3) or (len(tmp) == 2)) and
                                    tmp[1].isdigit()):
                                    element = tmp
                                    next_state = enum.GetAttrStates.RG_RESOURCE

                                # resoure.<alnum>.<ref> or resource.<alnum>
                                elif ((resource.grouptype == enum.Grouptypes.ASG) and
                                      ((len(tmp) == 3) or (len(tmp) == 2)) and
                                       tmp[1].isalnum()):
                                    element = tmp
                                    next_state = enum.GetAttrStates.ASG_RESOURCE

                                # resource.<name>
                                elif (len(tmp) == 2):
                                    element = tmp[1]
                                    next_state = enum.GetAttrStates.RESOURCE

                            # output name
                            else:
                                next_state = enum.GetAttrStates.OUTPUT_NAME
                else:
                    # element format can be only string
                    next_state = enum.GetAttrStates.ERROR

            # If second element is output name, resolve it
            elif cur_state == enum.GetAttrStates.OUTPUT_NAME:
                # Go through outputs section of resource file
                found = False
                for k, v in six.iteritems(resource.child.outputs):
                    if element == k:
                        value = v['value']
                        found = True
                        break

                # Output name not found
                if not found:
                    next_state = enum.GetAttrStates.ERROR
                else:
                    # If value is a get_
                    if ((type(value) == dict) and (len(value) == 1) and
                        ('get_' in list(value.keys())[0])):
                        value = resource.child.resolve_nested(value, name)

                        if value is None:
                            next_state = enum.GetAttrStates.ERROR
                            continue

                    index = index + 1
                    next_state = enum.GetAttrStates.OUTPUT_RESOLUTION


            # Rest of hierarchy
            elif cur_state == enum.GetAttrStates.OUTPUT_RESOLUTION:
                # End of hierarchy - now valid?
                if index >= len(hierarchy):
                    next_state = enum.GetAttrStates.RESOLVED
                    continue

                # Resolve nested element
                if type(hierarchy[index]) == dict:
                    element = self.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetAttrStates.ERROR

                elif ((type(element) == str) and (type(value) == dict) and
                      (element in value.keys())):
                    value = value[element]
                    index = index + 1

                # Value is n-th element in list
                elif ((type(element) == int) and (type(value) == list) and
                      (element < len(value))):
                    # TODO will it be parsed by YAML parser as int or str?
                    value = value[element]
                    index = index + 1

                else:
                    # element can only be string or digit
                    next_state = enum.GetAttrStates.ERROR

            # resource.<name>
            elif cur_state == enum.GetAttrStates.RESOURCE:
                found = False
                for r in resource.child.resources:
                    if element == r.name:
                        value = r
                        found = True
                        break
                # TODO: or can there be smth else?
                if ((not found) or (len(hierarchy) > (index + 1))):
                    next_state = enum.GetAttrStates.ERROR
                else:
                    next_state = enum.GetAttrStates.RESOLVED

            # resource.<number>(.<output>)
            elif (cur_state in (enum.GetAttrStates.RG_RESOURCE,
                                enum.GetAttrStates.ASG_RESOURCE)):

                # TODO can there be something after this? Current assumption is 'no'.
                if len(element) == 3:
                    # TODO is the third part output or resource inside the resource?
                    element = element[2]
                    next_state = enum.GetAttrStates.OUTPUT_NAME
                else:
                    next_state = enum.GetAttrStates.RESOLVED

            # 'attributes' or 'outputs' or 'outputs_list'
            # TODO: are these cases for any input any different?
            #       if not, make one case for all
            elif (cur_state in (enum.GetAttrStates.RG_ATTRIBUTES,
                                enum.GetAttrStates.ASG_OUTPUTS,
                                enum.GetAttrStates.ASG_OUTPUTS_LIST)):
                # Can it end here? Assumption - 'yes'
                if index >= len(hierarchy):
                    next_state = enum.GetAttrStates.RESOLVED
                    continue

                if type(hierarchy[index]) == dict:
                    element = self.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetAttrStates.ERROR
                else:
                    next_state = enum.GetAttrStates.OUTPUT_NAME


    def resolve_nested(self, nested_element, name):
        ''' Check format, tries to resolve element.
            Return its value upon success, None upon failure.
            nested_element - dictionary
            name - instance name
        '''

        if len(nested_element) == 1:
            # Resolve nested element
            return self.classify_items(list(nested_element.keys())[0],
                    list(nested_element.values())[0], name)
        else:
            # Not a get_function format
            return None


    def check_prop_par(self, parent, resource, environments):
        ''' Check properties against parameters and vice versa, tag used. '''

        # Find all differences - add to invalid references
        # Find all matches - merge into one object

        # Get difference in names of properties and parameters
        differences = list(set([x.name for x in self.params]) ^ set([y.name for y in resource.properties]))

        for diff in differences:
            found = False

            # Missing property for parameter
            for p in self.params:
                if diff == p.name:
                    found = True

                    # Only if parameter has no default
                    if p.default is None:
                        self.invalid.append(hotclasses.InvalidReference(
                                            diff, resource.name,
                                            enum.ErrorTypes.MISS_PROP, parent.path))
                        self.ok = False
                        break


            # Missing parameter for property
            if not found:
                for p in resource.properties:
                    if diff == p.name:
                        self.invalid.append(hotclasses.InvalidReference(
                                        diff, resource.name,
                                        enum.ErrorTypes.MISS_PARAM, self.path))
                        self.ok = False
                        break

        # Share PropertyParameter for each match
        for par in range(len(self.params)):
            for prop in resource.properties:
                if self.params[par].name == prop.name:
                    prop.merge(self.params[par])
                    self.params[par] = prop


    def depends_on(self):
        ''' Set resources which other resources depend on as used. '''

        for r in self.resources:
            if (r.structure is not None) and ('depends_on' in r.structure):
                found = False
                if type(r.structure['depends_on']) == str:
                    dependencies = [r.structure['depends_on']]
                elif type(r.structure['depends_on']) == list:
                    dependencies = r.structure['depends_on']
                else:
                    continue

                # Check dependencies
                for d in dependencies:
                   for x in self.resources:
                       if x.name == d:
                           x.used = True
                           found = True
                           break

                   if not found:

                       # Searched resource does not exist
                       self.invalid.append(hotclasses.InvalidReference(d, r.name,
                                           enum.ErrorTypes.DEPENDS_ON, None))
                       self.ok = False
