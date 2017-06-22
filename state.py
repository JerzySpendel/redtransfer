from functools import wraps


class StateMonitor:
    def __init__(self):
        pass

    @staticmethod
    def dispatch(*rules):

        def decorator(f):

            @wraps(f)
            def wrapper(*args, **kwargs):
                self = args[0]
                redirect_method_name = next((rule[1] for rule in rules if rule[0] == self.state), None)
                return getattr(self, redirect_method_name)(*args[1:], **kwargs)

            return wrapper

        return decorator
