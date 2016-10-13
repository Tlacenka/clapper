#!/usr/bin/env python
#coding=utf-8

# File: enum.py
# Brief: Additional classes defining enumeration types for HOT reference validator
# Classes: Fonts, TreeInfo, ErrorTypes, Grouptypes, GetAttrStates, GetParamStates
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

class Fonts:
    ''' Code for formatting output. '''
    BLUE      = '\033[94m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    ORANGE    = '\033[33m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    DEFAULT   = '\033[0m'


class TreeInfo:
    ''' Indicators of printed tree nodes. '''
    OTHER = 0
    LAST = 1 # Last sibling
    ONLY = 2 # Only one child

class ErrorTypes:
    ''' Enumerated reference get_ functions + properties:parameters reference. '''

    GET_RESOURCE  = 1 # get_resource
    GET_PARAM = 2     # get_param
    GET_ATTR = 3      # get_attr
    MISS_PROP  = 4    # parameter in file B does not have corresponding property in file A
    MISS_PARAM = 5    # property in file A does not have corresponding parameter in file B
    DEPENDS_ON = 6    # resource that other resource depends on does not exist
    ENV_PARAM = 7     # parameter value defined in env file has no match in root template
    ENV_PARAM_DEFAULT = 8 # parameter default value from env file has no match

class Grouptypes:
    ''' Resource types for groups of resources. '''
    ASG = 'OS::Heat::AutoScalingGroup'
    RG = 'OS::Heat::ResourceGroup'

class GetAttrStates:
    ''' Main states for initiating and ending FSM. '''
    INIT = 0
    RESOLVED = 1
    ERROR = 2

    # Keywords used for ASG, RG, special cases
    ASG_RESOURCE = 3      # 'resource.<alnum>.<resource name>' used
    RG_RESOURCE = 4       # 'resource.<number>.<resource name>' used
    RG_ATTRIBUTES = 5     # 'attributes' keyword used
    ASG_OUTPUTS_LIST = 6  # 'outputs_list' keyword used
    ASG_OUTPUTS = 7       # 'outputs' keyword used
    RESOURCE = 8          # 'resource.<name>' used

    # Usual cases
    RESOURCE_NAME = 9      # first element is a resource name
    OUTPUT_NAME  = 10       # second element is an output name
    OUTPUT_RESOLUTION = 11 # remaining element(s) as string/dictionary/list

class GetParamStates:
    ''' Main states for initiating and ending FSM. '''
    INIT = 0
    RESOLVED = 1
    ERROR = 2

    PARAM_NAME = 3         # first element is a parameter name
    PARAM_VALUE = 4        # find its value for further resolution
    PARAM_RESOLUTION = 5   # remaining element(s) as string/dictionary/list
