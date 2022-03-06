import os
import json
import types
import pytest
import tarfile
import logging

from pathlib import Path
from datetime import datetime
from functools import partial
from docker import DockerClient
from docker.models.images import Image
from docker.models.volumes import Volume
from docker.models.networks import Network
from typing import Callable, Generator, Union, Optional, List
from _pytest.config import Config
from src.tools.enums import ServiceType


_logger = logging.getLogger(__name__)


@pytest.fixture(name = 'log', autouse = True)
def fixture_log(request):
    _logger.info(f'====== Running: {request.node.name} ======')


@pytest.fixture(name = 'client', scope = 'session')
def fixture_client() -> DockerClient:
    """
    Yield a :py:class:`DockerClient`

    :return:    DockerClient
    """
    yield DockerClient()


@pytest.fixture(name = 'build', scope = 'session', autouse = True)
def fixture_build(pytestconfig, client: DockerClient) -> None:
    """
    Build the app image if we aren't in a CI

    :param pytestconfig:
    :param client:
    :return:
    """
    image_tag = pytestconfig.getoption("image_tag")
    if os.getenv('CI') is None:
        _logger.info(f'No CI detected. Building {image_tag}...')
        image, logs = client.images.build(
            path = '.',
            dockerfile = Path(pytestconfig.rootpath, 'src', 'docker', 'app.Dockerfile'),
            tag = image_tag,
            nocache = True,
            rm = True,
            buildargs = {
                'node_version': pytestconfig.getoption('node_version')
            }
        )
        for log in logs:
            if stream := log.get('stream'):
                _logger.info(stream)
    yield

    _logger.info(f'Removing image {image_tag}')
    client.images.remove(
        image = pytestconfig.getoption("image_tag")
    )


@pytest.fixture(name = 'network', scope = 'session')
def fixture_network(client: DockerClient) -> Callable:
    """
    Yield a callable to get the :py:class:`Network` for the containers

    :return:
    """
    def _func() -> Network:
        return client.networks.get(os.getenv('NETWORK'))

    yield _func


@pytest.fixture(name = 'image', scope = 'session')
def fixture_image(client: DockerClient) -> Callable:
    """
    Yield a callable to get the :py:class:`Image` for the containers

    :return:
    """
    def _func() -> Image:
        return client.images.get(os.getenv('IMAGE_BASE_TAG'))

    yield _func


@pytest.fixture(name = 'working_dir', scope = 'session')
def fixture_working_dir(pytestconfig) -> str:
    """
    Yield the name of the Image Working Directory

    :return:
    """
    yield os.getenv('WORKING_DIR')


@pytest.fixture(name = 'artifacts_dir', scope = 'session')
def fixture_artifacts_dir(pytestconfig: Config) -> Path:
    """
    Yield the location of the Artifacts folder for this run ``src/reports/(v<version>)``

    :param pytestconfig:
    :return:
    """
    yield Path(pytestconfig.rootpath, pytestconfig.getoption('artifacts'))


@pytest.fixture(name = 'rx_events', scope = 'session')
def fixture_rx_events(pytestconfig: Config, working_dir: str) -> Path:
    """
    Yield the location of the events.log in the Target container

    :return:
    """
    path = Path(pytestconfig.rootpath, 'src', 'app', ServiceType.TARGET.value, 'outputs.json')
    with path.open() as file:
        inputs = json.load(file)
        _logger.info(f'Loaded {file.name}...')

    yield Path(working_dir, inputs.get('file'))


@pytest.fixture(name = 'tx_events', scope = 'session')
def fixture_tx_events(pytestconfig: Config) -> Path:
    """
    Yield the local location of the agent event source file.

    :return:
    """
    path = Path(pytestconfig.rootpath, 'src', 'app', ServiceType.AGENT.value)
    with Path(path, 'inputs.json').open() as file:
        inputs = json.load(file)
        _logger.info(f'Loaded {file.name}...')

    yield Path(path, inputs.get('monitor'))


@pytest.fixture(name = 'reports', scope = 'session')
def fixture_reports(pytestconfig: Config) -> Path:
    """
    Yield the location of the reports folder

    :param pytestconfig:
    :return:
    """
    yield Path(pytestconfig.rootpath, 'src', 'reports')


@pytest.fixture(name = 'targz', scope = 'session', autouse = True)
def fixture_targz(reports: Path, artifacts_dir: Path) -> None:
    """
    During teardown, collect all items in the Artifacts folder and compress them

    :param reports:
    :param artifacts_dir:
    :return:
    """
    yield

    if os.getenv('CI'):
        with tarfile.open(name = str(Path(reports, f'{artifacts_dir.name}.tar.gz')), mode = 'w|gz') as tar:
            tar.add(str(artifacts_dir), artifacts_dir.name)
            _logger.info(f'Add {artifacts_dir.name} to {tar.name}')


@pytest.fixture(name = 'write_to_artifacts', scope = 'session')
def fixture_write_to_artifacts(artifacts_dir: Path) -> Callable:
    """
    Yield a Callable to allow writing content to the Artifacts directory.

    :param artifacts_dir:   The location of the Artifacts directory
    :return:
    """
    def _func(name: str, data: Union[bytes, Generator], extra_path: Path = '') -> Path:
        """
        Creates new file and writes the given data to the file. Returns the file name.

        :param name:        The name of the file
        :param data:        The data to be written
        :param extra_path:  Additional folders to create before writing the file to them
        :return:
        """
        path = Path(artifacts_dir, extra_path)
        path.mkdir(parents = True, exist_ok = True)

        with Path(path, name).open(mode = 'wb') as file:
            if isinstance(data, bytes):
                file.write(data)
            elif isinstance(data, (types.GeneratorType, list, tuple)):
                for chunk in data:
                    file.write(chunk)
            else:
                raise AssertionError(f'Writing {type(data)} to a file is not implemented')
            _logger.info(f'Created {name} at {path}')

        return Path(file.name)

    yield _func


@pytest.fixture(name = 'run_agent_cmd', scope = 'session')
def fixture_run_agent(client: DockerClient, image: Callable, network: Callable) -> Callable:
    """
    Yield a :py:class:`Callable`.

    When called will run the agent container and the ``node app.js agent`` command

    :param client:      The DockerClient
    :param image:       The Image instance
    :param network:     The Network instance
    :return:            Callable
    """
    def _func(_client: DockerClient) -> List[str]:
        """
        Call :py:method:`DockerClient.containers.run` on the image and run the app command

        :param _client: The DockerClient
        :return:        Generator
        """
        params = dict(
            image = image().short_id,
            command = ['node', 'app.js', ServiceType.AGENT.value],
            network = network().name,
            remove = True
        )

        _logger.info('Running Agent Container...')
        _logger.info(f'\n{json.dumps(params, indent = 4, sort_keys = True)}')
        return _client.containers.run(**params)

    yield partial(_func, client)


@pytest.fixture(name = 'logs', scope = 'session')
def fixture_logs(client: DockerClient) -> Callable[[str, Optional[datetime]], List[str]]:
    """
    Yield a :py:class:`Callable`.

    When called, will return the logs of a container from start or from a given timestamp.

    :param client:  A DockerClient
    :return:
    """
    def _func(_client: DockerClient, service: str, since: Optional[datetime] = None) -> List[str]:
        return _client.containers.get(service).logs(
            timestamps = True,
            since = since
        )

    yield partial(_func, client)

