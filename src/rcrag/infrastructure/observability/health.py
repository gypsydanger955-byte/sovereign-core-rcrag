from typing import Any, Tuple

def check_liveness() -> Tuple[bool, str]:
    """
    Liveness indicates the process is up.
    """
    return True, "alive"

def _try_call(obj: Any, method: str) -> Any:
    fn = getattr(obj, method, None)
    if fn is None:
        raise AttributeError
    if callable(fn):
        return fn()
    return fn

def check_readiness(historian: Any) -> Tuple[bool, str]:
    """
    Attempts a lightweight operation on the historian.
    Strategy:
    - Prefer 'ping'/'health'/'is_healthy' if available.
    - Else try 'count' or 'stats'.
    - Else try listing small subset via 'list'/'list_records' or similar with best-effort defaults.
    - Else assume healthy if no known method exists.
    Returns (ready, message)
    """
    try:
        for method in ("ping", "health", "is_healthy"):
            try:
                result = _try_call(historian, method)
                if isinstance(result, tuple) and len(result) == 2:
                    ok, msg = result
                    return bool(ok), str(msg)
                if isinstance(result, bool):
                    return bool(result), f"{method} ok" if result else f"{method} not ok"
                # If callable returns without error, consider ok
                return True, f"{method} ok"
            except AttributeError:
                continue

        # Try count-like methods
        for method in ("count", "get_count", "size", "len"):
            try:
                result = _try_call(historian, method)
                if isinstance(result, int) and result >= 0:
                    return True, "historian reachable"
                # If returned without exception, consider ok
                return True, "historian reachable"
            except AttributeError:
                continue

        # Try list-like methods
        for method in ("list", "list_records", "all", "list_all"):
            try:
                fn = getattr(historian, method)
                if callable(fn):
                    # Try a minimal call signature
                    try:
                        fn(limit=1)  # type: ignore
                    except TypeError:
                        try:
                            fn(1)  # type: ignore
                        except TypeError:
                            fn()  # type: ignore
                return True, "historian reachable"
            except AttributeError:
                continue

        # Try benign search
        for method in ("search", "query"):
            try:
                fn = getattr(historian, method)
                if callable(fn):
                    try:
                        fn("")  # type: ignore
                    except TypeError:
                        try:
                            fn(q="")  # type: ignore
                        except TypeError:
                            # last resort: call without args
                            fn()  # type: ignore
                return True, "historian reachable"
            except AttributeError:
                continue

        # No known method; consider ready if object exists
        return True, "historian object present"
    except Exception as e:
        return False, f"historian error: {e!r}"
