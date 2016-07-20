#!/usr/bin/env python
#coding=utf-8

# File: reference_valdator.py
# Brief: Main file running HOT reference validator
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

from __future__ import with_statement, print_function

import argparse
import sys

import YAML_HotValidator as VALIDATOR

def main():

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--unused', action='store_true',
                        help='When true, prints all unused resources/parameters.')
    parser.add_argument('-p', '--pretty-format', action='store_true',
                        help='When true, provides colourful output')
    parser.add_argument('-t', '--print-tree', action='store_true',
                        help='When true, output contains template structure')
    parser.add_argument('-e', '--environment', metavar='path/to/environment', nargs='+',
                        help='Environment files to be used.')
    parser.add_argument('-f', '--file', metavar='path/to/file',
                        help='HOT file to be used.')
    parser.add_argument('-n', '--nyan', action='store_true',
                        help='When true, prints nyanbar.')

    # Initialize validator
    validator = VALIDATOR.YAML_HotValidator(vars(parser.parse_args()))

    # Run validator
    validator.run()

    # Print results
    validator.print_output()

    sys.exit(0)

if __name__ == '__main__':
    main()
