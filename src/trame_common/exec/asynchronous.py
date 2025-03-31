import asyncio
import logging

__all__ = [
    "create_task",
    "decorate_task",
    "handle_task_result",
    "task",
]


def handle_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass  # Task cancellation should not be logged as an error.
    except Exception:  # pylint: disable=broad-except
        logging.exception("Exception raised by task = %r", task)


def decorate_task(task):
    """
    Decorate a task by attaching a done callback so any exception or error could
    be caught and reported.

    :param task: A coroutine to execute as an independent task
    :type task: asyncio.Task

    :return: The same task object
    :rtype: asyncio.Task
    """
    task.add_done_callback(handle_task_result)
    return task


def create_task(coroutine, loop=None):
    """
    Create a task from a coroutine while also attaching a done callback so any
    exception or error could be caught and reported.

    :param coroutine: A coroutine to execute as an independent task
    :param loop: Optionally provide the loop on which the task should be
                 scheduled on. By default we will use the current running loop.

    :return: The decorated task
    :rtype: asyncio.Task
    """
    if loop is None:
        loop = asyncio.get_event_loop()

    return decorate_task(loop.create_task(coroutine))


def task(func):
    """Function decorator to make its async execution within a task"""

    def wrapper(*args, **kwargs):
        create_task(func(*args, **kwargs))

    return wrapper
