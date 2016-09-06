#!/usr/bin/env python
#coding=utf-8

# File: reference_validator.py
# Brief: Main file running HOT reference validator
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import argparse
import sys

import hotvalidator

def main():

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--print-unused', action='store_true',
                        help='When true, prints all unused resources.')
    parser.add_argument('-p', '--pretty-format', action='store_true',
                        help='When true, provides colorful output')
    parser.add_argument('-t', '--print-tree', action='store_true',
                        help='When true, output contains template structure')
    parser.add_argument('-e', '--environment-file', metavar='path/to/environment', action='append',
                        help='Environment files to be used.')
    parser.add_argument('-f', '--template-file', metavar='path/to/file',
                        help='HOT file to be used.')
    parser.add_argument('-P', '--parameters', metavar='<KEY1=VALUE1;KEY2=VALUE2...>', action='append',
                        help='Parameter values used in the templates.')
    parser.add_argument('-n', '--nyan', action='store_true',
                        help='When true, prints nyanbar.')

    # Initialize validator
    validator = hotvalidator.HotValidator(vars(parser.parse_args()))

    # Run validator
    validator.run()

    # Print results
    validator.print_output()

    sys.exit(0)

if __name__ == '__main__':
    main()
