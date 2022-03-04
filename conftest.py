from pathlib import Path
from _pytest.config.argparsing import Parser


def pytest_addoption(parser: Parser):
    parser.addoption(
        '--artifacts',
        action = 'store',
        default = '',
        type = Path,
        help = 'Path to store any artifacts that are saved during the test run'
    )
