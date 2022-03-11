import pytest
import tarfile
import logging

from pathlib import Path
from typing import Callable
from docker import DockerClient
from itertools import permutations
from src.tools.enums import ServiceType
from src.tools.utils import event_check


_logger = logging.getLogger(__name__)


class TestApp:
    """
    **Test Flow** :
        **Setup**:
            - Start the Splitter and Target containers with the ``class_scoped_container_getter`` fixture
            - Run the Agent container (``node app.js agent``)
                - Store the output for later records

        **Tests**:
            - test_target_container_up_and_stable
            - test_splitter_container_up_and_stable
            - test_target_received_agent_events
            - test_events_stored_and_correct_at_target

        **Teardown**:
            - Store the Agent logs to the artifact directory
            - Store the Splitter and Target Logs to the artifacts directory
    """
    @pytest.fixture(name = 'start', scope = 'class', autouse = True)
    def fixture_start(self, class_scoped_container_getter, write_to_artifacts: Callable) -> None:
        """
        Start the Splitter/Target containers as defined in the docker-compose yaml.
            - The ``class_scoped_container_getter`` will use docker-compose up to start the container and
                wait for them to be up
            - Once this fixture goes out of scope, the containers will be torn down and removed along with the
                Network and Volumes

        :param class_scoped_container_getter:   pytest-docker-compose fixture
        :param write_to_artifacts:              Callable to write to the Artifact directory

        :return:
        """
        _logger.info(f'App is UP and Running...')
        yield
        for container in class_scoped_container_getter.docker_project.containers():
            write_to_artifacts(
                name       = f'{container.name}.log',
                data       = container.logs(),
                extra_path = self.__class__.__name__
            )

    @pytest.fixture(name = 'run', scope = 'class')
    def fixture_run(self, start, client: DockerClient, run_agent_cmd: Callable, write_to_artifacts: Callable) -> None:
        """
        Uses the ``run_agent_cmd`` fixture to run the Agent container.
            - Ensures that the Agent container is run before any tests in this class are executed

        :param start:               The start fixture (placement ensures it is called before this fixture)
        :param client:              A DockerClient
        :param run_agent_cmd:       A Callable to run the Agent node command/container
        :param write_to_artifacts:  Callable to write to the Artifact directory
        :return:
        """
        output = run_agent_cmd()
        yield
        write_to_artifacts(
            name = 'agent.log',
            data = output,
            extra_path = self.__class__.__name__
        )

    @staticmethod
    @pytest.mark.parametrize(
        'target',
        [
            'target_1', 'target_2'
        ]
    )
    def test_target_container_up_and_stable(client: DockerClient, target: str):
        """
        Verify the target containers are running the node command

        :param client:  A DockerClient
        :param target:  The hostname of the Target container
        :return:
        """
        container = client.containers.get(target)
        result = container.exec_run('pidof node app.js target')
        assert result.exit_code == 0, f'Startup command was not detected on {target}'

    @staticmethod
    def test_splitter_container_up_and_stable(client: DockerClient):
        """
        Verify the splitter container is running the node command

        :param client:  A DockerClient
        :return:
        """
        splitter = client.containers.get(ServiceType.SPLITTER)
        result = splitter.exec_run('pidof node app.js splitter')
        assert result.exit_code == 0, f'Startup command was not detected on splitter'

    @staticmethod
    @pytest.mark.parametrize(
        ('src', 'dst'),
        [
            pytest.param(src, dst, id = f'{src} -> {dst}') for src, dst in permutations(
                ['splitter', 'target_1', 'target_2'], r = 2
            )
        ]
    )
    def test_services_reachable_by_service(client: DockerClient, src: str, dst: str, ):
        """
        Verify each container is reachable by its Hostname

        :param client:  A DockerClient
        :param src:     The Source container hostname
        :param dst:     The Destination container hostname
        :return:
        """
        response = client.containers.get(src).exec_run(f'ping -c 5 -i .2 {dst}')
        _logger.info(f'{src} -> {dst}:\n{response.output.decode()}')
        assert response.exit_code == 0, f'Failed to reach {dst} from {src}'

    @staticmethod
    @pytest.mark.parametrize(
        'target',
        [
            'target_1', 'target_2'
        ]
    )
    @pytest.mark.usefixtures('run')
    def test_agent_connection_registered_at_target(client: DockerClient, target: str):
        """
        Verify the Target container logged the client connection

        :param client:  A DockerClient
        :param target:  The hostname of the Target container
        :return:
        """
        container = client.containers.get(target)

        # TODO: Could be going through a TON of logs. Should use fixture and 'since' option
        _logger.info(f"Looking for 'client connected' in {target} logs...")
        for log in container.logs().decode().split('\n'):
            if 'client connected' in log:
                _logger.info('  ...entry found.')
                break
        else:
            _logger.info('   ..entry not found')
            raise AssertionError(f'Unable to determine if the client connected to {target}')

    @staticmethod
    @pytest.mark.parametrize(
        'target',
        [
            'target_1', 'target_2'
        ]
    )
    @pytest.mark.usefixtures('run')
    def test_target_events_log_created(client: DockerClient, target: str, rx_events: Path):
        """
        Verify the Target container logged the client events

        :param client:  A DockerClient
        :param target:  The hostname of the Target container
        :return:
        """
        # Basic check for existence
        _logger.info(f'Searching for {rx_events} file...')
        result = client.containers.get(target).exec_run(f'test -f {rx_events.name}')
        assert result.exit_code == 0, f'The {rx_events.name} log was not found on {target}.'

    @pytest.mark.usefixtures('run')
    def test_events_stored_and_correct_at_targets(self, request, client: DockerClient, write_to_artifacts: Callable,
                                                  rx_events: Path, tx_events: Path):
        """
        Verify the Events received at the Target containers match the events in the monitor file

        :param client:              A DockerClient
        :param write_to_artifacts:  Callable to write to the Artifact directory
        :param rx_events:           The location of the events.log in the Target containers
        :param tx_events:           The location of the local monitor file
        :return:
        """
        targets = [
            container for container in client.containers.list()
            if container.labels.get('operation-mode') in [ServiceType.TARGET]
        ]

        logs = []
        for target in targets:
            # Grab the events.log from each Target
            _logger.info(f'Get Archive {rx_events.name} from {target.name}')
            result = target.exec_run(f'test -f {rx_events.name}')
            if result.exit_code == 0:
                stream, stats = client.api.get_archive(target.name, rx_events, encode_stream = True)
                log_name = f'{target.name}_events.tar'
                logs.append(
                    write_to_artifacts(
                        name = log_name,
                        data = stream,
                        extra_path = self.__class__.__name__
                    )
                )

        files = [tarfile.open(log, mode = 'r') for log in logs]
        for file in files:
            request.addfinalizer(file.close)

        partials = [file.extractfile(rx_events.name) for file in files]
        _logger.info(f'Determine if aggregate events in {rx_events.name} match {tx_events.name}')
        event_check(tx_events, *partials)
