# Mistral PoC

This is really rough. Basically, we add a Mistral action that runs a
shell script which runs ansible with a single validation.

## Prerequisites

You will need an undercloud with the mistral services running.

Assuming you have a recent enough instack-undercloud (Mitaka), the easiest is
to set `enable_mistral=true` in your 'undercloud.conf' file prior to running
`openstack undercloud install`. That's it.

On the undercloud, verify you have mistral_engine, mistral_api and
mistral_executor running with:

    $ pgrep -a mistral

You also need to have ansible installed on the undercloud:

    $ sudo pip install 'ansible<2'

The validation playbooks have only been tested with ansible 1.9.4 at the
moment.

Finaly, make sure `sudo` can run without the need for a tty. In `/etc/sudoers`
comment out the line "Defaults requiretty" if it's set.


## Mistral validation setup:

Install the `tripleo-validations` python module using the deploy.sh script:

    $ cd clapper/ansible-tests/mistral
    $ sudo ./deploy.sh

Load the `tripleo.validations` workbook:

    $ mistral workbook-create validations_workbook.yaml

## Running a validation using the mistral action

Run the `tripleo.run_validation` action with mistral client:

    mistral run-action -s tripleo.run_validation 512e

It will be run asynchronously and store the result in the mistral DB. Run
`mistral action-execution-list` to see the status of all Mistral runs and
`mistral action-execution-get-output <uuid>` to get a particular run's output.

The output is whatever dict we return from our Python code converted to json.

## Running validations using the mistral workflow

Create an json context file containing the arguments passed to the workflow:

    {
      "validation_names": ["512e", "rabbitmq-limits"]
    }

Run the `tripleo.validations.run` workflow with mistral client:

    mistral execution-create tripleo.validations.run context.json

## TODO

* actions to:
  * get validation groups
  * run a group of validations
* ton of other stuff
