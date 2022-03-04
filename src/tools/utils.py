import json

from pathlib import Path
from typing import IO, Union


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
