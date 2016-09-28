#!/usr/bin/env python
#coding=utf-8

# File: hotfile.py
# Brief: Class HotFile for validating HOT files
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

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


    def load_file(self, curr_nodes, templates, environments, curr_path):
        ''' Validates YAML file. '''

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
            print('ERROR in file ' + self.path + ': ' + str(err), file=sys.stderr)
            sys.exit(1)

        # Save all parameters names, resources and properties
        if 'parameters' in self.structure:
            for param in self.structure['parameters'].items():
                self.params.append(hotclasses.PropertyParameter(param, True))

        # Save name and structure of each resource
        if 'resources' in self.structure:
            for key, value in six.iteritems(self.structure['resources']):
                self.resources.append(hotclasses.Resource(key, value, self))

        # Save outputs
        if 'outputs' in self.structure:
            for key, value in six.iteritems(self.structure['outputs']):
                self.outputs[key] = value

        # Examine children nodes to get the full information about references
        for resource in self.resources:
            if resource.type.endswith('.yaml'):
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
        ''' After loading information, validates references in file.'''

        # Add current node at the beginning
        curr_nodes.append(self)

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


    def get_param_FSM(self, hierarchy, name):
        ''' Validates get_param
            hierarchy - reference
            name - instance name
        '''

        # main variables: cur_state, next_state, value
        cur_state = enum.GetParamStates.INIT
        next_state = enum.GetParamStates.INIT

        parameter = None # Referenced parameter
        value = None # Searched value

        element = None # Value of current element (string)
        index = 0 # Index of current element

        while True:

            # State transition
            cur_state = next_state

            # Initiate resolution
            if cur_state == enum.GetParamStates.INIT:
                if (type(hierarchy) == list) and (len(hierarchy) > 0):
                    next_state = enum.GetAttrStates.PARAM_NAME
                else:
                    next_state = enum.GetAttrStates.ERROR

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
                parameter.used = True
                return value

            # Find parameter
            elif cur_state == enum.GetParamStates.PARAM_NAME:
                if type(hierarchy[index]) == dict:
                    element = self.resolve_nested(hierarchy[index], name)
                else:
                    element = hierarchy[index]

                if element is None:
                    next_state = enum.GetParamStates.ERROR

                elif type(element) == str:
                    for p in self.params:
                        if p.name == hierarchy[index]:
                            parameter = value = p
                            break
                    

    def get_param(self, hierarchy, name):
        ''' Validates get_param
            hierarchy - reference
            name - instance name
        '''
        if type(hierarchy) == list:

            error = None

            # Get root - parameter and its structure
            parameter = None
            for p in self.params:
                if p.name == hierarchy[0]:
                    parameter = p
            if parameter is None:
                error = hierarchy[0]

            # Get its value
            if error is None:

                # Try validating based on property
                get_value = None
                if parameter.value is not None:

                    get_value = parameter.value

                    # If property value is referenced by get_
                    if ((type(parameter.value) == dict) and
                        (len(get_value.items()) == 1) and
                        ('get_' in list(get_value.keys())[0])):

                            # Checks if parent file content is available
                            if isinstance(self.parent, HotFile):
                                get_value = self.parent.classify_items(
                                    list(get_value.keys())[0],
                                    list(get_value.values())[0], name)
                            # If not?
                            else:
                                pass

                            if get_value is None:
                                error = hierarchy[0]

                # Validate based on parameter only
                else:
                    if parameter.default is not None:
                        get_value = parameter.default
                    else:
                        error = hierarchy[0]

            # Get value of the rest of the hierarchy
            if error is None:
               for i in range(1, len(hierarchy)):
                   if type(hierarchy[i]) == str:
                       # TODO points to smth in a group, check if it is a group
                       if hierarchy[i].isdigit():
                           pass
                       else:
                           # Try finding value of key in current structure
                           if type(get_value) is not dict:
                              error = hierarchy[i]
                              break

                           else:
                               found = False
                               for k, v in six.iteritems(get_value):
                                   if k == hierarchy[i]:
                                       get_value = v
                                       found = True
                                       break

                               if not found:
                                  error = hierarchy[i]
                                  break

                   elif type(hierarchy[i]) == int: # in case of a list, which position
                       pass

                   elif type(hierarchy[i]) == dict: # nested get_
                       kv = hierarchy[i].items()[0]

                       if type(self.parent) == HotFile:
                          get_value = self.parent.classify_items(kv[0], kv[1], name)
                          if get_value is None:
                             error = hierarchy[i]
                   else:
                       error = hierarchy[i]

            if error is not None:
                # Add it to invalid references
                self.invalid.append(hotclasses.InvalidReference(hierarchy[1], name,
                                    enum.ErrorTypes.GET_PARAM, None))
                self.ok = False
                return None

            else:
               # Change usage flag
               par = [x for x in self.params if x.name == hierarchy[0]][0]
               if (par is not None) and (par.used == False):
                   par.used = True

               # Return reference value
               return get_value

        elif type(hierarchy) == str:
            # Check if it is a pseudoparameter
            if hierarchy not in ['OS::stack_name', 'OS::stack_id', 'OS::project_id']:
                if hierarchy not in [x.name for x in self.params]:
                    # Add it to invalid references
                    self.invalid.append(hotclasses.InvalidReference(hierarchy, name,
                                         enum.ErrorTypes.GET_PARAM, None))
                    self.ok = False
                    return None

                else:
                    # Changes usage flag
                    par = [x for x in self.params if x.name == hierarchy][0]
                    if par.used == False:
                        par.used = True
                    # Returns parameter value or default value
                    return (par.value if par.value is not None else par.default)
        else:
             # Add it to invalid references
             self.invalid.append(hotclasses.InvalidReference(hierarchy, name,
                                 enum.ErrorTypes.GET_PARAM, None))
             self.ok = False
             return None


    def get_resource(self, hierarchy, name):
        ''' Validates get_resource
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

    def get_attr_FSM(self, hierarchy, name):
        ''' Validates get_attr
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
                if type(hierarchy) == list:
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
                        if r.name == hierarchy[index]:
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
                            # 'resource.<name>', 'resource.<number>' or 'resource.<number>.<name>'
                            elif element.startswith('resource.'):
                                tmp = element.split('.')
                                
                                # resource.<number>.<ref> or resource.<number>
                                if ((resource.grouptype == enum.Grouptypes.RG) and
                                    ((len(tmp) == 3) or (len(tmp) == 2)) and
                                    tmp[1].isdigit()):
                                    element = tmp
                                    next_state = enum.GetAttrStates.RG_RESOURCE

                                # resource.<name>
                                elif (len(tmp) == 2):
                                    element = tmp[1]
                                    next_state = enum.GetAttrStates.RESOURCE

                            # TODO: Add resource.<alphanumeric string>... for ASG
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

                # Value is n-th element in list
                elif ((type(element) == int) and (type(value) == list) and
                      (element < len(value))):
                    # TODO will it be parsed by YAML parser as int or str?
                    value = value[element]

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
            elif cur_state == enum.GetAttrStates.RG_RESOURCE:
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
            elif (cur_state in [enum.GetAttrStates.RG_ATTRIBUTES,
                                enum.GetAttrStates.ASG_OUTPUTS,
                                enum.GetAttrStates.ASG_OUTPUTS_LIST]):
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
        ''' Checks format, tries to resolve element.
            Returns its value upon success, None upon failure.
            nested_element - dictionary
            name - instance name
        '''

        if len(nested_element) == 1:
            # Resolve nested element
            return self.classify_items(nested_element.keys()[0], 
                    nested_element.values()[0], name)
        else:
            # Not a get_function format
            return None
        

    def get_attr(self, hierarchy, name):
        ''' Validates get_attr
            hierarchy - reference
            name - instance name
        '''

        error = None

        if type(hierarchy) == list:

            if len(hierarchy) < 2:
                error = hierarchy[0]

            # Root is a resource - find root
            if error is None:
                get_value = None
                for r in self.resources:
                    if r.name == hierarchy[0]:
                        get_value = r
                        break

                if get_value is None:
                    error = hierarchy[0]

            cur_resource = get_value # for flagging usage

            if error is None:
                # Find output and its value

                # If child node is not a yaml file, return non-None value
                if get_value.child is None:
                    cur_resource.used = True
                    return get_value

                # resource.<name> used
                if hierarchy[1].startswith('resource.'):
                    string = hierarchy[1].split('.')
                    found = False
                    if r.grouptype == '':
                        for r in get_value.child.resources:
                            if string[1] == r.name:
                                get_value = r
                                found = True
                                break
                    # TODO longer hierarchy
                    elif r.grouptype == enum.Grouptypes.RG:
                        for k, v in six.iteritems(get_value.child.outputs):
                            if ((string[2] == k) and (type(v) == dict) and
                                ('value' in v.keys())):
                                get_value = v['value']
                                found = True
                                break

                    if not found:
                        error = hierarchy[1]
                    else:
                        cur_resource.used = True
                        return get_value

                 # TODO longer hierarchy
                 # "attributes" returns in ResourceGroup { "server0" -> {"name": ..., "ip": ...}, "server1" -> {"name": ..., "ip": ...} }
                 # - dictionary where keys are names of resources in that group, values are resource attributes
                elif ((get_value.grouptype == enum.Grouptypes.RG) and
                      (len(hierarchy) >= 3) and (hierarchy[1] == 'attributes')):
                    for k, v in six.iteritems(get_value.child.outputs):
                        if ((hierarchy[2] == k) and (type(v) == dict) and
                                ('value' in v.keys())):
                            get_value = v['value']
                            found = True
                            break

                    if not found:
                        error = hierarchy[1]
                    else:
                        cur_resource.used = True
                        return get_value

                # outputs_list used in case of autoscaling group TODO list?
                elif ((get_value.grouptype == enum.Grouptypes.ASG) and
                      (len(hierarchy) >= 3) and (hierarchy[1] == 'outputs_list')):
                    print(get_value.name, get_value.hotfile.path)
                    found = False
                    for k, v in six.iteritems(get_value.child.outputs):
                        if ((k == hierarchy[2]) and (type(v) is dict) and
                            ('value' in v.keys())):
                            cur_file = get_value.child
                            get_value = v['value']
                            found = True
                            break

                    if not found:
                        error = hierarchy[1]
                    else:
                        # If the value is in get_, validate nested get_
                        if ((type(get_value) is dict) and (len(get_value.keys()) == 1) and
                            ('get_' in list(get_value.keys())[0])):
                            get_value = cur_file.classify_items(
                                list(get_value.keys())[0],
                                list(get_value.values())[0], name)

                            if get_value is None:
                                error = hierarchy[1] # TODO tag nested

                        # Validate rest of the hierarchy
                        if error is None:
                            for i in range(3, len(hierarchy)):
                                if type(get_value) != dict:
                                    error = hierarchy[i]
                                    break

                                # Nested get_
                                if ((type(hierarchy[i]) == dict) and
                                    ('get_' in list(hierarchy[i].keys())[0])):
                                    nested_get_value = self.classify_items(
                                        list(hierarchy[i].keys())[0],
                                        list(hierarchy[i].values())[0], name)

                                    if ((nested_get_value is None) or
                                        (type(nested_get_value) != str) or
                                        (nested_get_value not in get_value.keys())):
                                        error = 'nested ' + list(hierarchy[i].keys())[0]
                                        break
                                    else:
                                        get_value = get_value[nested_get_value]

                                elif ((type(hierarchy[i]) == str) and
                                      (hierarchy[i] in get_value.keys())):
                                    get_value = get_value[value[i]]
                                else:
                                    if type(hierarchy[i]) == str:
                                        error = hierarchy[i]
                                    else:
                                        error = 'nested ' + list(hierarchy[i].keys())[0] + ' - ' + list(hierarchy[i].values()[0])[0]
                                    break

                        if error is None:
                            cur_resource.used = True
                            return get_value

                # normally mapped to outputs section
                # TODO remove duplicate sections from outputs_list and outputs
                else:
                    # Find output
                    found = False
                    for k, v in six.iteritems(get_value.child.outputs):
                        if hierarchy[1] == k:
                            cur_file = get_value.child
                            get_value = v
                            found = True
                            break
                    if not found:
                        error = hierarchy[1]
                    if error is None:
                        # Go to value section of the output
                        if ((type(get_value) == dict) and
                            ('value' in get_value.keys())):
                            get_value = get_value['value']
                        else:
                            error = hierarchy[1]

                    # Value can be dictionary or string
                    if error is None:
                        if type(get_value) == dict:
                            # str_replace or list_join
                            if (('str_replace' in get_value.keys()) or
                                (('list_join') in get_value.keys())):
                                pass

                            # get_
                            elif ((len(get_value.keys()) == 1) and
                                  ('get_' in list(get_value.keys())[0])):
                                  get_value = cur_file.classify_items(
                                      list(get_value.keys())[0],
                                      list(get_value.values())[0], name)

                                  if get_value is None:
                                      error = hierarchy[1]

                            # else - structured value
                        elif type(get_value) != str:
                            error = hierarchy[1]

                    if error is None:
                        # Get subvalues of value from other elements of the get_attr list
                        for i in range(2, len(hierarchy)):
                            if type(get_value) != dict:
                                error = hierarchy[i]
                                break

                            # Nested get_
                            if ((type(hierarchy[i]) == dict) and
                                ('get_' in list(hierarchy[i].keys())[0])):
                                nested_get_value = self.classify_items(
                                    list(hierarchy[i].keys())[0],
                                    list(hierarchy[i].values())[0], name)

                                if ((nested_get_value is None) or
                                    (type(nested_get_value) != str) or
                                    (nested_get_value not in get_value.keys())):
                                    error = 'nested ' + list(hierarchy[i].keys())[0]
                                    break
                                else:
                                    get_value = get_value[nested_get_value]

                            elif ((type(hierarchy[i]) == str) and
                                  (hierarchy[i] in get_value.keys())):
                                get_value = get_value[hierarchy[i]]
                            else:
                                if type(hierarchy[i]) == str:
                                    error = hierarchy[i]
                                else:
                                    error = 'nested ' + list(hierarchy[i].keys())[0] + ' - ' + list(hierarchy[i].values()[0])[0]
                                break


        # Is there any other format of get_attr than a list?
        else:
            error = 'type of get_attr value is ' + type(hierarchy)

        # Return value or None
        if error is None:
            cur_resource.used = True
            return get_value
        else:
            self.invalid.append(hotclasses.InvalidReference(error,
                                name + ' - output of ' + hierarchy[0],
                                enum.ErrorTypes.GET_ATTR, None))
            self.ok = False
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

                    if (p.default is None):
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
        ''' Sets resources which other resources depend on as used '''

        for r in self.resources:
            if 'depends_on' in r.structure:
                found = False
                if type(r.structure['depends_on']) == str:
                    dependencies = [r.structure['depends_on']]
                elif type(r.structure['depends_on']) == list:
                    dependencies = r.structure['depends_on']

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
