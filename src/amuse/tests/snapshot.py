import inspect
from os import mkdir, path


SNAPSHOT_DIR_NAME = 'snapshots'


def resolve_snapshot(filename, source_file_path):
    """
    Builds path to `./snapshot` dir relative to a file path.

    Function is input path agnostic, but file path
    is most likely a path to a test file when used
    with the `snapshot_test` decorator.
    """
    source_dir_path = path.realpath(path.dirname(source_file_path))
    snapshot_dir_path = path.join(source_dir_path, SNAPSHOT_DIR_NAME)
    if not path.isdir(snapshot_dir_path):
        mkdir(snapshot_dir_path)
    snapshot_file_path = path.join(snapshot_dir_path, filename)
    return Snapshot(snapshot_file_path)


def snapshot_test(cls):
    """
    Decorator adding `.assertEqualSnapshot` method to a TestCase.
    """
    caller_path = inspect.getfile(cls)

    def assertEqualSnapshot(self, value, snapshot_name):
        """
        Compliments `TestCase.assertEqual` to unify how snapshots
        are read, written, and where they can be found.
        """
        snapshot = resolve_snapshot(snapshot_name, caller_path)

        if not snapshot.exists():
            snapshot.write(value)

        self.assertEqual(value, snapshot.read())

    cls.assertEqualSnapshot = assertEqualSnapshot

    return cls


class Snapshot(object):
    """
    Class representing a Snapshot file,
    simplifying reading and writing contents.
    """

    def __init__(self, path):
        self.path = path

    def exists(self):
        return path.isfile(self.path)

    def read(self):
        with open(self.path, 'rb') as file:
            return file.read()

    def write(self, data):
        with open(self.path, 'wb') as file:
            file.write(data)
