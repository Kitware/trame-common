import importlib.metadata

import trame_common as m


def test_version():
    assert importlib.metadata.version("trame_common") == m.__version__
