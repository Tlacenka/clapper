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
 - ``-f`` is an absolute/relative path to root HOT template
 - ``-e`` is an absolute/relative path to environment file(s)
 - ``-p/--pretty-format`` when selected, the output is colourful
 - ``-u/--print-unused`` causes printing additional info (unused instances without reference)
 - ``-n/--nyan`` causes printing nyanbar
 - ``-t/--print-tree`` when selected, output also contains tree template structure

<h2> Output </h2>
Script prints the result to standard output. The result contains a list of all associated files containing invalid references and info about involved instances.
Optionally, it also prints a list of all unused instances.

<h2> Files </h2>

 - ``reference_validator.py`` contains the main file that runs the validation based on parameters
 - ``YAML_HotValidator.py`` contains corresponding class and encapsulates validator behaviour
 - ``YAML_Hotfile.py`` contains corresponding class that realizes the file validation itself
 - ``YAML_Enums.py`` contains all classes used for enumeration ( ``YAML_colours``, ``YAML_Types``, ``YAML_tree_info``)
 - ``YAML_HotClasses.py`` contains the rest of the classes used for validation ( ``YAML_Env``, ``YAML_Prop_Par``, ``YAML_Resource``, ``YAML_Reference``)
