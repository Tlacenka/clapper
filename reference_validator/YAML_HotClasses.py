#!/usr/bin/env python
#coding=utf-8

# File: YAML_HotClasses.py
# Brief: Additional classes used for HOT reference validation
# Classes: YAML_Env, YAML_Prop_Par, YAML_Reference, YAML_Resource
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import YAML_Enums as ENUM
import YAML_Hotfile as HOT

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

class YAML_Resource:
    ''' Stores useful info about resource, its structure. '''
    def __init__(self, name, hotfile, resource_struct):

        self.structure = resource_struct
        self.type = resource_struct['type']
        self.child = None      # child node
        self.name = name       # name of resource variable
        self.hotfile = hotfile # name of file containing resource
        self.properties = []   # list of YAML_ParProp
        self.used = False      # usage flag

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
                #print (self.name, self.type)
                for prop in resource_struct['properties']['resource' if
                            self.grouptype == 'OS::Heat::AutoScalingGroup' else 'resource_def']['properties'].items():
                    self.properties.append(YAML_Prop_Par(prop, False))
            else:
                for prop in resource_struct['properties'].items():
                    self.properties.append(YAML_Prop_Par(prop, False))


class YAML_Reference:
    ''' Saves all invalid references for output. In YAML_Hotfile. '''

    def __init__(self, referent, element, ref_type, parent):
        self.referent = referent # name of referred element
        self.element = element   # in which resource was reference realized
        self.type = ref_type     # type of referred attribute (YAML_Types)
        self.parent = parent     # used in property reference
