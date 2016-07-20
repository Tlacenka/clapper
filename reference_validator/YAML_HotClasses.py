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
        self.parent = parent_node   # parent node
        self.children = []          # children env files

        self.resource_registry = {} # original type: mapped type [, resource]
        self.params = {}            # additional parameters, only for root file -f
        self.params_default = {}    # default values, can replace property in property>param anywhere

        self.structure = {}         # file structure
        self.invalid = []           # invalid parameter references

        self.ok = True              # validation status

class YAML_Prop_Par:
    ''' Class for saving information about parameters and properties.
        Each parameter and its corresponding property share one. '''

    def __init__(self, structure, isPar):
        self.name = structure[0]    # name of parameter/property
        self.used = False           # flag of usage (reference)
        self.type = None            # parameter type

        self.value = (None if isPar else structure[1]) # value (possibly structured)
        self.default = None         # default value

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
    def __init__(self, name, value, hot):
        self.name = name                    # name of resource variable
        self.structure = value              # resource structure
        self.type = value['type']           # resource type (filename if mapped)
        self.used = False                   # usage flag

        self.hotfile = hot                  # file containing resource
        self.child = None                   # child node

        self.properties = []                # list of YAML_ParProp

        self.isGroup = False # is it a group type
        self.grouptype = ''

        if self.type in [ENUM.YAML_Grouptypes.ASG, ENUM.YAML_Grouptypes.RG]:
            self.isGroup = True

        props = []


        # If there are properties, save them
        if 'properties' in value:
            # Type and properties of the individual resource
            if self.isGroup:
                self.grouptype = self.type
                if self.grouptype == ENUM.YAML_Grouptypes.ASG:
                    self.type = self.structure['properties']['resource']['type']
                else:
                    self.type = self.structure['properties']['resource_def']['type']

                # Load properties
                for prop in self.structure['properties'][('resource' if
                            self.grouptype == ENUM.YAML_Grouptypes.ASG else 'resource_def')]['properties'].items():
                    self.properties.append(YAML_Prop_Par(prop, False))
            else:
                for prop in self.structure['properties'].items():
                    self.properties.append(YAML_Prop_Par(prop, False))


class YAML_Reference:
    ''' Saves all invalid references for output. In YAML_Hotfile. '''

    def __init__(self, referent, element, ref_type, parent):
        self.referent = referent # name of referred element
        self.element = element   # in which resource was reference realized
        self.type = ref_type     # type of referred attribute (YAML_Types)
        self.parent = parent     # used in property reference
