Reference Validator
===================

<h2> Introduction </h2>

This script goes through all HOT files associated with root template, taking mapped resources from environment files into account.
It validates references and detects unused variables/instances in YAML files. It accepts the same basic parameters as heat (root template and environments).
The script is tested on tripleo-heat-templates repository using overcloud-resource-registry-puppet Puppet environment.
It is currently under development but it should be already able to validate most of the HOT correctly.

<h2> Requirements </h2>

 - pyyaml
 - six
 - nyanbar (for Python 2.x)

<h2> Usage </h2>

    $ python[3] reference_validator.py -f <path/to/yaml/root template> -e <path/to/yaml/environment file> [<another/path/to/env/files>] [-p/--pretty-format] [-u/--print-unused] [-n/--nyan] [-h/--help] [-t/--print-tree]

<h3> Parameters </h3>
 - ``-f/--template-file`` is an absolute/relative path to root HOT template
 - ``-e/--environment-file`` is an absolute/relative path to environment file(s)
 - ``-p/--pretty-format`` when selected, the output is colourful
 - ``-P/--parameters`` enables inserting additional parameters for template file
 - ``-u/--print-unused`` causes printing additional info (unused instances without reference)
 - ``-n/--nyan`` causes printing nyanbar
 - ``-t/--print-tree`` when selected, output also contains tree template structure

<h2> Output </h2>
Script prints the result to standard output. The result contains a list of all associated files containing invalid references and info about involved instances.
Optionally, it also prints a list of all unused instances.

<h2> Files </h2>

 - ``reference_validator.py`` contains the main file that runs the validation based on parameters
 - ``hotvalidator.py`` contains corresponding class and encapsulates validator behaviour
 - ``hotfile.py`` contains corresponding class that realizes the file validation itself
 - ``enum.py`` contains all classes used for enumeration ( ``Fonts``, ``TreeInfo``, ``ErrorTypes``, ``GroupTypes``, ``GetAttrStates``, ``GetParamStates``)
 - ``hotclasses.py`` contains the rest of the classes used for validation ( ``Environment``, ``PropertyParameter``, ``Resource``, ``InvalidReference``)

<h2> Tests </h2>
In order to validate the script, tests were created. Testing environment is created in `tests` folder. In this folder,
there are following subfolders:
 - `test_files` containing files - HOT and environment files demonstrating different scenarios. These files also include comments about errors and warnings in the tested HOT.
    As the validator does not end after coming across the first error, these comments help readability.
 - `test_logs` containing log files that are gained by running validator on test files and consist of standard error output and standard output stream.
 - `test_diffs` containing files that consist of expected validator output and are to be compared with logs during the testing process.
 
Testing is realized by executing a script called `run_tests.sh` which is located in the `reference_validator` folder.


<h3> Usage </h3>

    $ ./run_tests.sh [-c] [-v]

  - ``-c`` when selected, log files are automatically removed after the testing process is finished
  - ``-v`` when selected, diff between expected and actual output is included directly in the test script output
