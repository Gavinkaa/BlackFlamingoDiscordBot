import time
from functools import wraps


class OnCooldownError(Exception):
    def __init__(self, time):
        self.retry_after = time.real

    def __str__(self):
        return f"The function is on cooldown for {self.retry_after} seconds."


def cooldown(duration, nb_calls=1):
    def decorator(method):
        call_list = []

        @wraps(method)
        def wrapper(*args, **kwargs):
            nonlocal call_list
            _update_list()
            if len(call_list) < nb_calls:
                call_list.append(time.time())
                return method(*args, **kwargs)
            raise OnCooldownError(duration + call_list[0] - time.time())

        def _update_list():
            nonlocal call_list
            call_list = [x for x in call_list if x > time.time() - duration]

        return wrapper

    return decorator
