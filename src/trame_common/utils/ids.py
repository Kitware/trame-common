import itertools

__all__ = [
    "next_id",
]

_COUNTER = itertools.count(1)


def next_id():
    """
    Return a new process-wide unique id, as a lowercase hex string with the
    ``0x`` prefix: "0x1", "0x2", ... "0xa", ...

    Every type of object agents reach takes its id from this generator, so
    their ids never collide. The prefix makes an id easy to recognize, and since a
    name starts with a letter or an underscore, a name can never be mistaken
    for an id.
    """
    return _to_id(next(_COUNTER))


def _to_id(value):
    return f"0x{value:x}"
