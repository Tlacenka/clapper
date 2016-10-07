#!/usr/bin/env python
#coding=utf-8

# File: hotclasses.py
# Brief: Additional classes used for HOT reference validation
# Classes: Environment, PropertyParamater, InvalidReference, Resource
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import enum

class Environment:
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

class PropertyParameter:
    ''' Class for saving information about parameters and properties.
        Each parameter and its corresponding property share one.
    '''

    def __init__(self, structure, isPar):
        self.name = structure[0]    # name of parameter/property
        self.used = False           # flag of usage (reference)
        self.type = None            # parameter type
        self.hidden = False         # hidden property (for passwords etc)

        self.value = (None if isPar else structure[1]) # value (possibly structured)
        self.default = None         # default value

        if isPar and (structure[1] is not None) and ('type' in structure[1]):
            self.type = structure[1]['type']

        if isPar and (structure[1] is not None) and ('default' in structure[1]):
            self.default = structure[1]['default']

        if isPar and (structure[1] is not None) and ('hidden' in structure[1]):
            self.hidden = structure[1]['hidden']

    def clone(self):
        ''' Create a deep copy of the object,
            mutable objects such as structure are shared.
        '''
        new_propar = PropertyParameter((self.name, None), True)

        # Copies all values to the clone
        new_propar.type = self.type
        new_propar.hidden = self.hidden
        new_propar.value = self.value
        new_propar.default = self.default

        return new_propar

    def merge(self, obj):
        ''' Merge 2 objects, use attributes of the second object if they are defined.
            obj = parameter
        '''

        # Cannot merge with None
        if obj is None:
            return

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

class Resource:
    ''' Store useful info about resource, its structure. '''
    def __init__(self, name, value, hot):
        self.name = name                    # name of resource variable
        self.structure = value              # resource structure

        self.type = ''

        if ((self.structure is not None) and ('type' in self.structure) and
            (self.structure['type'] is not None)):
            self.type = value['type']       # resource type (filename if mapped)
        self.used = False                   # usage flag

        self.hotfile = hot                  # file containing resource
        self.child = None                   # child node

        self.properties = []                # list of ParProp

        self.isGroup = False # is it a group type
        self.grouptype = ''

        if self.type in [enum.Grouptypes.ASG, enum.Grouptypes.RG]:
            self.isGroup = True

        props = []


        # If there are properties, save them
        if (self.structure is not None) and ('properties' in self.structure):

            # Type and properties of the individual resource
            if self.isGroup:
                self.grouptype = self.type

                if ((self.grouptype == enum.Grouptypes.ASG) and
                    ('resource' in self.structure['properties']) and
                    ('type' in self.structure['properties']['resource'])):
                    self.type = self.structure['properties']['resource']['type']
                elif ((self.grouptype == enum.Grouptypes.RG) and
                      ('resource_def' in self.structure['properties']) and
                      ('type' in self.structure['properties']['resource_def'])):
                    self.type = self.structure['properties']['resource_def']['type']
                else:
                    # No properties found
                    return

                # Load properties
                for prop in self.structure['properties'][('resource' if
                            self.grouptype == enum.Grouptypes.ASG else 'resource_def')]['properties'].items():
                    self.properties.append(PropertyParameter(prop, False))
            else:
                if self.structure['properties'] is not None:
                    for prop in self.structure['properties'].items():
                        self.properties.append(PropertyParameter(prop, False))

    def clone(self):
        ''' Create a new deep copy of the object,
            mutable objects such as structure are shared.
        '''
        new_resource = Resource(self.name, self.structure, self.hotfile)
        return new_resource

class InvalidReference:
    ''' Save all invalid references for output, used in hotfile. '''

    def __init__(self, referent, element, ref_type, parent):
        self.referent = referent # name of referred element
        self.element = element   # in which resource was reference realized
        self.type = ref_type     # type of referred attribute (ErrorTypes)
        self.parent = parent     # used in property reference
