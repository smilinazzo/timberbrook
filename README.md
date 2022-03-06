# TimberBrook

## Description

> TimberBrook is a test implementation for a Splitter Application. The Splitter will receive *events* from an Agent 
> service and randomly distribute the events between a number of target services. 

## Approach

### Tools/Packages
* **pytest**:
  * The pytest framework makes it easy to write small, readable tests, and can scale to support complex functional testing for applications and libraries.
* **pytest-docker-compose**:
  * A plugin for pytest that allows for the startup/teardown/cleanup of containers/volumes/networks using docker-compose and fixtures
* **docker** (SDK):
  * The docker python SDK allows for interaction with images/container through a DockerClient instance

### Implementation

For this project, there is a single *Test Suite* in `src/tests/integration/test_integration` in a Test Class 
called `TestApp`. 

With the `pytest-docker-compose` plugin, we are passing in a `docker-compose` yaml 
(`src/docker/docker-app-compose.yml`) and using a class-scoped fixture to start the `splitter` and `target` containers.
This was done to allow for the containers to be setup/torndown in multiple scenarios and have control over when the 
`Agent` service was launched.

For the `TestApp` tests, the `Agent` service is started after `docker-compose` has determined the startup of its 
services is complete. The `Agent` command *node app.js agent* is run before any tests execute and validations of state, 
connectivity, logging, and results are made. After which, all containers, volumes, and networks are torn down 
regardless of tests success or failure.

Container logs, the Target's events.log file, and test logs are stored in the `src/reports` directory as Artifacts. 

## Tests

* **Test 1**: Verify the Target containers are up and stable
>  * Purpose:
>    * To determine the container is available and running its cmd: *node app.js target*
>  * Method:
>    * Makes an exec call to the container to check the process is running
>  * Pass Criteria:
>    * The result of the exec has an exit code of 0

* **Test 2**: Verify the Splitter container is up and stable
>  * Purpose:
>    * To determine the container is available and running its cmd: *node app.js splitter*
>  * Method:
>    * Makes an exec call to the container to check the process is running
>  * Pass Criteria:
>    * The result of the exec has an exit code of 0

* **Test 3**: Verify the Splitter and Target containers are reachable by hostnames
>  * Purpose:
>    * To determine the containers are on the same network and can reach each other over `timbernet`
>  * Method:
>    * Makes an exec call to the source container to ping the dest container
>  * Pass Criteria:
>    * The result of the exec has an exit code of 0

* **Test 4**: Verify the Target containers registered the Agent operation by logging the connection
>  * Purpose:
>    * To determine the Target container detected the connection and logged the events
>  * Method:
>    * Parses the available container logs for a string
>      * **Note**: Not the strongest way of determining success since log strings can change
>  * Pass Criteria:
>    * The 'client connected' string is found in the log file of the Target container

* **Test 6**: Verify the Target created a log file of the events
>  * Purpose:
>    * To determine the Target container recorded the logs to the file declared in `src/app/target/outputs.json`
>  * Method:
>    * Makes an exec call to the container to check the file exists
>      * **Note**: We are assuming that the file doesn't exist already. Could add fixture checks to make sure of this.
>  * Pass Criteria:
>    * The result of the exec has an exit code of 0

* **Test 7**: Verify the aggregate of the Target events.log files matches the file declared in `src/app/agent/inputs/large_1M_events.log`
>  * Purpose:
>    * To determine the Splitter correctly distributed the received events to each target
>  * Method:
>    * Grabs the file from each Target container
>    * Extracts the events.log and passes that file descriptor and the agent master file to a file comparison method
>      * `src/tools/utils.py:file_cmp`:
>        * Read the first line of each file and store it in a hash keyed by an index
>        * For each line in the master file, look for the matching line in the hash values
>        * If its found AND there are no duplicates in the values:
>           * read the next line from the corresponding file and store it in that hash location
>           * continue
>        * If it is not found OR there are duplicates, fail
>       * **Note**: It is assumed for this that the events are recorded in order so the events.log files are sorted.
>  * Pass Criteria:
>      * The result search is None
 
**Point of Note**:
I can't get *Test 7* to pass on the Git Hosted runner (self-hosted passes). There seems to be some corruption or issue with writing the events.log. 
* On the Self-Hosted runner, all of the events are written in consistent chunks/order and the test passes. 
* On the GitHub Ubuntu, the events are written, but I will see overlap and out-of-order entries. For example:

The test will fail with an error like this:
    E   AssertionError: The event: [This is event number 78085]
    E   was not found in: ['target_1_events.tar', 'target_2_events.tar']
    E     Last:
    E       0: event number 82940    
    E       1: This is event number 80512
 
Meaning we were looking for event 78085, but the line in the both file didn't match as they were already at event 8XXXX (as well as the line in the first file being incomplete).

That entry actually appears in target_1 events.log. But here:

    This is event number 85364
    This is event number 85365
    This is event number 85366
    This is event This is event number 78085
    This is event number 78086
    This is event number 78087
    This is event number 78088

So, the data chunk that was supposed to be written before the 8XXXX chunk is actually written after. I haven't been able to explain this failure and it's keeping me up at nights.


## Deployment

### Requirements
* Linux (Tested on: Mint 20.03)
* Docker (Tested on: 20.10.12)
* Docker-Compose (Tested on: 1.29.2)
* Python3 and pip3 (Tested on: 3.8.10/20.0.2)

### Setup
1. Create a git directory
> mkdir git

2. Pull the repo
> git clone git@github.com:smilinazzo/timberbrook.git

3. Change to the timberbrook directory
> cd timberbrook

4. Install the requirements
> pip3 install -r requirements.txt

5. Run the tests
> python3 -m pytest --image_tag=cribl/app-image

or
> pytest --image_tag=cribl/app-image

### Artifacts
Console logs, Container logs, and output files are saved to `src/reports`
