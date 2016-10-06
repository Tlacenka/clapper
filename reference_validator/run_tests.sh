#!/bin/bash

# File: run_tests.sh
# Brief: Script for running reference validator tests
# Author: Katerina Pilatova (kpilatov)
# Date: 2016
# Usage: ./run_tests.sh [-c]

# Fonts
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
BOLD=$(tput bold)
BLUE=$(tput setaf 4)
DEFAULT=$(tput sgr0)

# Test variables
TESTS=()
ELEMENTS=2
CLEAN=false # Remove logs afterwards

LOG_DIR=tests/test_logs
DIFF_DIR=tests/test_diffs

# Load tests
TEST01=("Test 1 - Parsing valid YAML file:" \
        "sudo python reference_validator.py -f tests/test_files/01_root.yaml -u")

TEST02=("Test 2 - Parsing invalid YAML file:" \
        "sudo python reference_validator.py -f tests/test_files/02_root.yaml -u")

TEST03=("Test 3 - Parsing valid HOT with missing section structure:" \
        "sudo python reference_validator.py -f tests/test_files/03_root.yaml -e tests/test_files/03_env.yaml -u")

TEST04=("Test 4 - Parsing valid HOT with missing instance structure:" \
        "sudo python reference_validator.py -f tests/test_files/04_root.yaml -u")

TEST05=("Test 5 - Parsing valid HOT with missing instance property structure:" \
        "sudo python reference_validator.py -f tests/test_files/05_root.yaml -u")

TEST06=("Test 6 - Basic HOT resolution:" \
        "sudo python reference_validator.py -f tests/test_files/06_root.yaml -e tests/test_files/06_env.yaml -u")

#TEST07=("Test 7 - Advanced HOT resolution:" \
#        "sudo python reference_validator.py -f tests/test_files/07_root.yaml -e tests/test_files/07_env1.yaml -e test_files/07_env2.yaml -u")

TESTS=("${TEST01[@]}" "${TEST02[@]}" "${TEST03[@]}" "${TEST04[@]}")
TESTS+=("${TEST05[@]}" "${TEST06[@]}")

TESTS_NR=`expr ${#TESTS[@]} / $ELEMENTS`

# Function for running tests
function run_test() {

    # Run command - both stderr and stdout go to the same log file
    ${2} >$LOG_DIR/${3}.log 2>&1

    # Diff log and expected log
    OUTPUT=`diff $LOG_DIR/${3}.log $DIFF_DIR/${3}.diff`

    # Print result
    if [[ -z "$OUTPUT" ]]; then
        printf "${1} ${GREEN}OK${DEFAULT}\n"
    else
        printf "${1} ${RED}FAILED${DEFAULT}\n"
    fi

}

# Main

# Setting -c parameter
if [[ "$1" = "-c" ]]
then
   CLEAN=true
fi

# Remove log files if they exist

# Run tests in loop
printf "${BOLD}Running YAML reference validator tests${DEFAULT}\n"

# Add zero padding
for T in $(seq -f "%02g" 1 $TESTS_NR)
do
   run_test "${TESTS[@]:$(( (T - 1) * ELEMENTS )):$ELEMENTS}" $T
done

# Remove log files if -c is set
if [ "$CLEAN" = true ]
then
   rm tests/test_logs/*.log
fi

exit
