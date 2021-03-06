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
VERBOSE=false # prints diff if test failed

LOG_DIR=tests/test_logs
DIFF_DIR=tests/test_diffs
PYTHON=python
PYTHON3=python3

# Load tests
TEST01=("Test 1 - Parsing valid YAML file:" \
        "reference_validator.py -f tests/test_files/01_root.yaml -u")

TEST02=("Test 2 - Parsing invalid YAML file:" \
        "reference_validator.py -f tests/test_files/02_root.yaml -u")

TEST03=("Test 3 - Parsing valid HOT with missing section structure:" \
        "reference_validator.py -f tests/test_files/03_root.yaml -e tests/test_files/03_env.yaml -u")

TEST04=("Test 4 - Parsing valid HOT with missing instance structure:" \
        "reference_validator.py -f tests/test_files/04_root.yaml -u")

TEST05=("Test 5 - Parsing valid HOT with missing instance property structure:" \
        "reference_validator.py -f tests/test_files/05_root.yaml -u")

TEST06=("Test 6 - Basic HOT resolution:" \
        "reference_validator.py -f tests/test_files/06_root.yaml -e tests/test_files/06_env.yaml -u")

TEST07=("Test 7 - Advanced HOT resolution:" \
        "reference_validator.py -f tests/test_files/07_root.yaml -e tests/test_files/07_env1.yaml -e tests/test_files/07_env2.yaml -u")

TESTS=("${TEST01[@]}" "${TEST02[@]}" "${TEST03[@]}" "${TEST04[@]}")
TESTS+=("${TEST05[@]}" "${TEST06[@]}" "${TEST07[@]}")

TESTS_NR=`expr ${#TESTS[@]} / $ELEMENTS`

# Function for running tests
function run_test() {

    # Run command - both stderr and stdout go to the same log file
    ${4} ${2} >$LOG_DIR/${3}.${4}.log 2>&1

    # Diff log and expected log
    OUTPUT=`diff $LOG_DIR/${3}.${4}.log $DIFF_DIR/${3}.${4}.diff`

    # Print result
    if [[ -z "$OUTPUT" ]]; then
        printf "${1} ${GREEN}OK${DEFAULT}\n"
    else
        printf "${1} ${RED}FAILED${DEFAULT}\n"

        # Print diff output if verbose option is set
        if [ "$VERBOSE" = true ]
        then
            # yellow - current (unexpected) output
            # red - expected output that is missing
            echo "$OUTPUT" 2>&1 | GREP_COLOR='01;33' egrep --color=always '<|$' \
                                | GREP_COLOR='01;31' egrep -i --color=always '>|$'
        fi
    fi

}

# Main

# Parse arguments
while [[ $# -gt 0 ]]
do
    key="$1"

    case $key in
        -v|--verbose)
        VERBOSE=true
        ;;

        -c|--clean)
        CLEAN=true
        ;;

        *)
            >&2 echo "Unknown argument."
            exit 1
        ;;
    esac
    shift # past argument or value
done

# Run tests in loop
printf "${BOLD}Running YAML reference validator tests for python${DEFAULT}\n"

# Add zero padding
for T in $(seq -f "%02g" 1 $TESTS_NR)
do
   run_test "${TESTS[@]:$(( (T - 1) * ELEMENTS )):$ELEMENTS}" $T $PYTHON
done

printf "${BOLD}Running YAML reference validator tests for python 3${DEFAULT}\n"

# Add zero padding
for T in $(seq -f "%02g" 1 $TESTS_NR)
do
   run_test "${TESTS[@]:$(( (T - 1) * ELEMENTS )):$ELEMENTS}" $T $PYTHON3
done

# Remove log files if -c is set
if [ "$CLEAN" = true ]
then
   rm tests/test_logs/*.log
fi

exit
