#!/usr/bin/env python
#coding=utf-8

# File: YAML_Enums.py
# Brief: Additional classes defining enumeration types for HOT reference validator
# Classes: YAML_colours, YAML_tree_info, YAML_Types
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

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

class YAML_Types:
    ''' Enumerated reference get_ functions + properties:parameters reference. '''

    GET_RESOURCE  = 1 # get_resource
    GET_PARAM = 2     # get_param
    GET_ATTR = 3      # get_attr
    MISS_PROP  = 4    # parameter in file B does not have corresponding property in file A
    MISS_PARAM = 5    # property in file A does not have corresponding parameter in file B
    DEPENDS_ON = 6    # resource that other resource depends on does not exist
