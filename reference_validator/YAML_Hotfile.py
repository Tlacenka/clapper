#!/usr/bin/env python
#coding=utf-8

# File: YAML_Hotfile.py
# Brief: Class YAML_Hotfile for validating HOT files
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import os
import sys
import six  # compatibility
import yaml # pip install pyyaml

import YAML_Enums as ENUM
import YAML_HotClasses

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
                self.params.append(YAML_HotClasses.YAML_Prop_Par(param, True))

        # Save name and structure of each resource
        if 'resources' in self.structure:
            for resource in self.structure['resources']:
                self.resources.append(YAML_HotClasses.YAML_Resource(resource, self,
                                      self.structure['resources'][resource]))

        # Save outputs
        if 'outputs' in self.structure:
            for out in self.structure['outputs']:
                self.outputs[out] = self.structure['outputs'][out]

        # Examine children nodes to get the full information about references
        for resource in self.resources:
            if resource.type.endswith('.yaml'):
                templates.insert(0, YAML_Hotfile(self, resource.type))

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

        # Check dependencies
        self.check_depends_on()
        
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
       else:
           return None


    def check_get_parameter(self, value, name):
        ''' Validates get_param
            value - reference
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
                #print ('error get_param 1')

            # Get its value
            if error is None:

                # Try validating based on property
                get_value = None
                if root.value is not None:
                     if type(root.value) == str:
                          get_value = root.value
                     elif type(root.value) == dict:

                         # Get all nested get_ from property
                         get_value = root.value
                         while ((type(get_value) == dict) and
                             (len(get_value.items()) == 1) and
                             ('get_' in list(get_value.keys())[0])):

                             if isinstance(self.parent, YAML_Hotfile):
                                 get_value = self.parent.classify_items(list(get_value.keys())[0], list(get_value.values())[0], name)
                                 #print (self.parent.path, kv, get_value)

                         if get_value is None:
                             error = value[0]
                             #print ('error get_param 3', value)
                             
                # Validate based on parameter only
                else:
                    if root.default is not None:
                        get_value = root.default
                    else:
                        error = value[0]
                        #print ('error get_param 4')

            # Get value of the rest of the hierarchy
            if error is None:
               for i in range(1, len(value)):
                   if type(value[i]) == str:
                       if value[i].isdigit(): # TODO points to smth in a group, check if it is a group
                           pass
                       else:
                           # Try finding value of key in current structure
                           if type(get_value) is not dict:
                              error = value[i]
                              #print ('error get_param 5', get_value)
                              break

                           else:
                               flag = False
                               for k, v in six.iteritems(get_value):
                                   if k == value[i]:
                                       get_value = v
                                       flag = True
                                       break

                               if not flag:
                                  error = value[i]
                                  #print ('error get_param 6')
                                  break

                   elif type(value[i]) == int: # in case of a list, which position
                       pass

                   elif type(value[i]) == dict: # nested get_
                       kv = value[i].items()[0]
                       
                       if type(self.parent) == YAML_Hotfile:
                          get_value = self.parent.classify_items(kv[0]. kv[1], name)
                          if get_value is None:
                             #print ('error get_param 7')
                             error = value[i]
                   else:
                       #print ('error get_param 8')
                       error = value[i]

            if error is not None:
                # Add it to invalid references
                self.invalid.append(YAML_HotClasses.YAML_Reference(value[1], name,
                                    ENUM.YAML_Types.GET_PARAM, None))
                self.ok = False
                return None

            else:
               # Change usage flag
               par = [x for x in self.params if x.name == value[0]][0]
               if (par is not None) and (par.used == False):
                   par.used = True

               # Return reference value
               return get_value

        elif type(value) == str:
            # Check if it is a pseudoparameter
            if value not in ['OS::stack_name', 'OS::stack_id', 'OS::project_id']:
                if value not in [x.name for x in self.params]:
                    # Add it to invalid references
                    self.invalid.append(YAML_HotClasses.YAML_Reference(value, name,
                                         ENUM.YAML_Types.GET_PARAM, None))
                    self.ok = False
                    return None

                else:
                    # Changes usage flag
                    par = [x for x in self.params if x.name == value][0]
                    if par.used == False:
                        par.used = True
                    # Returns parameter value or default value
                    return (par.value if par.value is not None else par.default)
        else:
             # Add it to invalid references
             self.invalid.append(YAML_HotClasses.YAML_Reference(value, name,
                                 ENUM.YAML_Types.GET_PARAM, None))
             self.ok = False
             return None


    def check_get_resource(self, value, name):
        ''' Validates get_resource
            value - reference
            name - instance name
        '''

        for r in self.resources:
            if value == r.name:
                r.used = True
                return r

        # If not found, add it to invalid references
        self.invalid.append(YAML_HotClasses.YAML_Reference(value, name,
                            ENUM.YAML_Types.GET_RESOURCE, None))
        self.ok = False
        return None


    def check_get_attribute(self, value, name):
        ''' Validates get_attr
            value - reference
            name - instance name
        '''

        error = None

        if type(value) == list:

            if len(value) < 2:
                error = value[0]
                #print ('error get_attr 1')

            # Root is a resource - find root
            if error is None:
                get_value = None
                for r in self.resources:
                    if r.name == value[0]:
                        get_value = r
                        break

                if get_value is None:
                    error = value[0]
                    #print ('error get_attr 2')

            cur_resource = get_value # for flagging usage

            if error is None:
                # Find output and its value

                # If child node is not a yaml file, return non-None value
                if get_value.child is None:
                    cur_resource.used = True
                    return get_value

                # resource.<name> used
                if value[1].startswith('resource.'):
                    string = value[1].split('.')
                    flag = False
                    if r.grouptype == '':
                        for r in get_value.child.resources:
                            if string[1] == r.name:
                                get_value = r
                                flag = True
                                break
                    # TODO longer hierarchy
                    elif r.grouptype == 'OS::Heat::ResourceGroup':
                        for k, v in six.iteritems(get_value.child.outputs):
                            if ((string[2] == k) and (type(v) == dict) and
                                ('value' in v.keys())):
                                get_value = v['value']
                                flag = True
                                break
                            
                    if not flag:
                        error = value[1]
                        #print ('error get_attr 3')
                    else:
                        cur_resource.used = True
                        return get_value

                 # TODO longer hierarchy
                 # "attributes" vrati u ResourceGroup { "server0" -> {"name": ..., "ip": ...}, "server1" -> {"name": ..., "ip": ...} }
                 # - slovnik kde klice jsou jmena resources v te resource group a hodnoty jsou atributy tech resourcu 
                elif ((get_value.grouptype == 'OS::Heat::ResourceGroup') and
                      (len(value) >= 3) and (value[1] == 'attributes')):
                    for k, v in six.iteritems(get_value.child.outputs):
                        if ((value[2] == k) and (type(v) == dict) and
                                ('value' in v.keys())):
                            get_value = v['value']
                            flag = True
                            break

                    if not flag:
                        error = value[1]
                        #print ('error get_attr 3')
                    else:
                        cur_resource.used = True
                        return get_value

                # outputs_list used in case of autoscaling group TODO list?
                elif ((get_value.grouptype == 'OS::Heat::AutoScalingGroup') and
                      (len(value) >= 3) and (value[1] == 'outputs_list')):
                    flag = False
                    for k, v in six.iteritems(get_value.child.outputs):
                        if ((k == value[2]) and (type(v) is dict) and
                            ('value' in v.keys())):
                            cur_file = get_value.child
                            get_value = v['value']
                            flag = True
                            break

                    if not flag:
                        error = value[1]
                        #print ('error get_attr 4')
                    else:
                        # If the value is in get_, validate nested get_
                        if ((type(get_value) is dict) and (len(get_value.keys()) == 1) and
                            ('get_' in list(get_value.keys())[0])):
                            get_value = cur_file.classify_items(list(get_value.keys())[0], list(get_value.values())[0], name)
                            if get_value is None:
                                error = value[1] # TODO tag nested
                                #print ('error get_attr 5')

                        # Validate rest of the hierarchy
                        if error is None:
                            for i in range(3, len(value)):
                                if type(get_value) != dict:
                                    error = value[i]
                                    #print ('error get_attr 6')
                                    break

                                # Nested get_
                                if ((type(value[i]) == dict) and
                                    ('get_' in list(value[i].keys())[0])):
                                    nested_get_value = self.classify_items(list(value[i].keys())[0], list(value[i].values())[0], name)
                                    if ((nested_get_value is None) or
                                        (type(nested_get_value) != str) or
                                        (nested_get_value not in get_value.keys())):
                                        error = 'nested ' + list(value[i].keys())[0]
                                        #print ('error get_attr 7')
                                        break
                                    else:
                                        get_value = get_value[nested_get_value]
                            
                                elif ((type(value[i]) == str) and
                                      (value[i] in get_value.keys())):
                                    get_value = get_value[value[i]]
                                else:
                                    if type(value[i]) == str:
                                        error = value[i]
                                    else:
                                        error = 'nested ' + list(value[i].keys())[0] + ' - ' + list(value[i].values())[0][0]
                                    #print ('error get_attr 8')
                                    break

                        if error is None:
                            cur_resource.used = True
                            return get_value

                # normally mapped to outputs section
                # TODO remove duplicate sections from outputs_list and outputs
                else:
                    # Find output
                    flag = False
                    for k, v in six.iteritems(get_value.child.outputs):
                        if value[1] == k:
                            cur_file = get_value.child
                            get_value = v
                            flag = True
                            break
                    if not flag:
                        error = value[1]
                        print ('error get_attr 9')
                    if error is None:
                        # Go to value section of the output
                        if ((type(get_value) == dict) and
                            ('value' in get_value.keys())):
                            get_value = get_value['value']
                        else:
                            error = value[1]
                            #print ('error get_attr 10')

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
                                  get_value = cur_file.classify_items(list(get_value.keys())[0], list(get_value.values())[0], name)
                                  if get_value is None:
                                      error = value[1]
                                      #print ('error get_attr 11')

                            # else - structured value
                        elif type(get_value) != str:
                            error = value[1]
                            #print ('error get_attr 12')

                    if error is None:
                        # Get subvalues of value from other elements of the get_attr list
                        for i in range(2, len(value)):
                            if type(get_value) != dict:
                                error = value[i]
                                #print ('error get_attr 13')
                                break

                            # Nested get_
                            if ((type(value[i]) == dict) and
                                ('get_' in list(value[i].keys())[0])):
                                nested_get_value = self.classify_items(list(value[i].keys())[0], list(value[i].values())[0], name)
                                if ((nested_get_value is None) or
                                    (type(nested_get_value) != str) or
                                    (nested_get_value not in get_value.keys())):
                                    error = 'nested ' + list(value[i].keys())[0]
                                    #print ('error get_attr 14')
                                    break
                                else:
                                    get_value = get_value[nested_get_value]
                            
                            elif ((type(value[i]) == str) and
                                  (value[i] in get_value.keys())):
                                get_value = get_value[value[i]]
                            else:
                                if type(value[i]) == str:
                                    error = value[i]
                                else:
                                    error = 'nested ' + list(value[i].keys())[0] + ' - ' + list(value[i].values())[0][0]
                                #print ('error get_attr 15')
                                break


        # Is there any other format of get_attr than a list?
        else:
            error = 'type of get_attr value is ' + type(value)
            #print ('error get_attr 16')

        # Return value or None
        if error is None:
            #print (get_value)
            cur_resource.used = True
            return get_value
        else:
            #print ('error get_attr', name, error)
            self.invalid.append(YAML_HotClasses.YAML_Reference(error, name +
                                ' - output of ' + value[0],
                                ENUM.YAML_Types.GET_ATTR, None))
            self.ok = False
            return None


    def check_prop_par(self, parent, resource, environments):
        ''' Check properties against parameters and vice versa, tag used. '''

        # Get difference in names of properties and parameters
        differences = list(set([x.name for x in self.params]) ^ set([y.name for y in resource.properties]))

        for diff in differences:
            # Missing property for parameter
            if diff in [x.name for x in self.params]:
                if [True for x in self.params if (x.name == diff) and (x.default is None)]:
                    self.invalid.append(YAML_HotClasses.YAML_Reference(diff, resource.name,
                                        ENUM.YAML_Types.MISS_PROP, parent.path))
                    self.ok = False
            # Missing parameter for property
            elif diff in [x.name for x in resource.properties]:
                #print ('missing param for property', diff, resource.name)
                self.invalid.append(YAML_HotClasses.YAML_Reference(diff, resource.name,
                                    ENUM.YAML_Types.MISS_PARAM, self.path))
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

    def check_depends_on(self):
        ''' Sets resources which other resources depend on as used '''
        for dependent in self.resources:
            if 'depends_on' in dependent.structure:
                flag = False
                if type(dependent.structure['depends_on']) == str:
                    dependencies = [dependent.structure['depends_on']]
                else:
                    dependencies = dependent.structure['depends_on']
                for d in dependencies:
                   for r in self.resources:
                       if r.name == d:
                           r.used = True
                           flag = True
                           break

                   if not flag:
                       # Searched resource does not exist
                       self.invalid.append(YAML_HotClasses.YAML_Reference(d, dependent.name,
                                           ENUM.YAML_Types.DEPENDS_ON, None))
                       self.ok = False
        return True
