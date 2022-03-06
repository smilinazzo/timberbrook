import os

from pathlib import Path
from _pytest.config.argparsing import Parser
from src.tools.logger import init_config


def pytest_addoption(parser: Parser):
    parser.addoption(
        '--artifacts',
        action = 'store',
        default = 'src/reports',
        type = Path,
        help = 'Path to store any artifacts that are saved during the test run'
    )
    parser.addoption(
        '--image_tag',
        action = 'store',
        default = os.getenv('IMAGE_BASE_TAG'),
        required = os.getenv('IMAGE_BASE_TAG') is None,
        help = 'The image_tag to tag the build image'
    )
    parser.addoption(
        '--node_version',
        action = 'store',
        default = 'current',
        help = 'Desired Node Version to build Image'
    )


def pytest_configure(config):
    # Set ENVs
    if (image := config.getoption('image_tag')) is not None:
        os.environ['IMAGE_BASE_TAG'] = image
    if os.getenv('NETWORK') is None:
        os.environ['NETWORK'] = 'timbernet'
    if os.getenv('WORKING_DIR') is None:
        os.environ['WORKING_DIR'] = '/app'

    artifact_dir = config.getoption('artifacts')
    Path(artifact_dir).mkdir(exist_ok = True)

    init_config(
        Path(
            artifact_dir,
            'timberbrook.log'
        )
    )

