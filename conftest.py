from pathlib import Path
from _pytest.config.argparsing import Parser
from src.tools.logger import init_config


def pytest_addoption(parser: Parser):
    parser.addoption(
        '--artifacts',
        action = 'store',
        default = '',
        type = Path,
        help = 'Path to store any artifacts that are saved during the test run'
    )


def pytest_configure(config):
    init_config(
        Path(
            config.getoption('artifacts'),
            'timberbrook.log'
        )
    )

