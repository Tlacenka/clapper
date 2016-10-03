#!/bin/bash

# File: run_tests.sh
# Brief: Script for running reference validator tests
# Author: Katerina Pilatova (kpilatov)
# Date: 2016

echo 'Test 1 - Parsing valid YAML file:'
sudo python reference_validator.py -f test_files/01_root.yaml -u -p

echo 'Test 2 - Parsing invalid YAML file:'
sudo python reference_validator.py -f test_files/02_root.yaml -u -p

echo 'Test 3 - Parsing valid HOT with missing section structure:'
sudo python reference_validator.py -f test_files/03_root.yaml -e test_files/03_env.yaml -u -p

echo 'Test 4 - Parsing valid HOT with missing instance structure:'
sudo python reference_validator.py -f test_files/04_root.yaml -u -p

echo 'Test 5 - Parsing valid HOT with missing instance property structure:'
sudo python reference_validator.py -f test_files/05_root.yaml -u -p

echo 'Test 6 - Basic HOT resolution:'
sudo python reference_validator.py -f test_files/06_root.yaml -e test_files/06_env.yaml -u -p
