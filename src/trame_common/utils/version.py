try:
    # Use importlib metadata if available (python >=3.8)
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    # No importlib metadata. Try to use pkg_resources instead.
    from pkg_resources import (
        DistributionNotFound as PackageNotFoundError,
    )
    from pkg_resources import (
        get_distribution,
    )

    def version(x):
        return get_distribution(x).version


__all__ = [
    "get_version",
]


def get_version(package_name):
    try:
        return version(package_name)
    except PackageNotFoundError:
        # package is not installed
        pass
