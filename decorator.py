import time
from functools import wraps


class OnCooldownError(Exception):
    def __init__(self, time):
        self.retry_after = time.real

    def __str__(self):
        return f"The function is on cooldown for {self.retry_after} seconds."


