import json
import logging

from pathlib import Path
from typing import IO, Union
from prettytable import PrettyTable

_logger = logging.getLogger(__name__)


def event_check(master: Union[str, Path], *files: IO[bytes]) -> None:
    results = {'valid': 0, 'duplicate': 0, 'missing': 0, 'invalid': 0}
    table = PrettyTable(field_names = results.keys())

    _logger.info('Start Master Event search...')
    with open(master, mode = 'rb') as source:
        # Read in all master events
        master_events = {
            event: 0 for event in source.readlines()
        }
        invalid = 0

        while any(events := [file.readline() for file in files]):
            # While there is an event record remaining in a target file, record the result
            for event in events:
                if event:
                    status = master_events.get(event)
                    if status is None:
                        # Event was not found
                        invalid += 1
                    else:
                        master_events[event] += 1

    # Compile results
    results['invalid'] = invalid
    for value in master_events.values():
        if value == 0:
            results['missing'] += 1
        elif value == 1:
            results['valid'] += 1
        else:
            results['duplicate'] += 1

    table.add_row(results.values())
    _logger.info(f'\n{table}')

    assert results['duplicate'] == results['missing'] == invalid == 0, f'Event errors found:\n{table}'


def file_cmp(master: Union[str, Path], *files: IO[bytes]) -> None:
    """
    Attempt to find each *event* in ``master`` in the given file descriptors::

    Raises and :py:class:`AssertionError` if:
        - Master File is exhausted and events still exist in files
        - Duplicate events found in files
        - Extra events found in files

    :param master:  The location of the Master file
    :arg files:     The file descriptors to search
    :return:
    """
    current = {
        idx: file.readline().decode().strip() for idx, file in enumerate(files)
    }

    with open(master, mode = 'rb') as source:
        while master_line := source.readline().decode().strip():
            # If masterFile is empty, all file readlines should be as well
            if not master_line:
                assert all(line == '' for line in current.values()), \
                    f'Events detected in files with an empty {master} file'

            # Are all lines unique?
            lines = list(current.values())
            if len(set(lines)) != len(lines):
                raise AssertionError(
                    'Duplicate events were found:\n'
                    f'{json.dumps([line for line in lines if line], indent = 4)}'
                )

            # Check each file for the line
            for file_no, line in current.items():
                if line == master_line:
                    print(f'Found [{master_line}] in {files[file_no].name}')
                    current[file_no] = files[file_no].readline().decode().strip()
                    break
            else:
                lines = '    \n'.join(f'{name}: {line if line else "<empty>"}' for name, line in current.items())
                raise AssertionError(
                    f'The event: [{master_line}]\n'
                    f'was not found in: {[file.name for file in files]}\n'
                    f'  Last:\n{lines}'
                )

        assert all(line == '' for line in current.values()), \
            f'Extra Events detected in files:\n{json.dumps([line for line in lines if line], indent = 4)}'
