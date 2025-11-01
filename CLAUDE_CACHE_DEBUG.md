The core issue here is that your `CacheHistorianDecorator.__getattr__` method returns a *new async function wrapper* every time you access a cacheable method (like `get_record`). This means:

- First call to `cached.get_record` returns a wrapper function **A**.
- Second call to `cached.get_record` returns a different wrapper function **B**.
- The cache (`self._cache`) lives on the decorator instance.
- But the cache update only happens inside the wrapper function returned by `__getattr__`.
- The problem: Because `cached.get_record` returns a new wrapper each time, the cache mutation happens only inside each wrapper's context and perhaps the cache state appears to be fresh.
- Possibly, the problem is that the cache mutable state is not shared correctly or the cache updates are not visible.

But more concretely, after reading your code carefully, this pattern is problematic:

```python
def __getattr__(self, name: str):
    target = getattr(self._inner, name)
    if not self._is_cacheable(name, target):
        return target

    async def wrapper(*args, **kwargs):
        # caching logic including self._cache updates
        ...
    return wrapper
```

Because every time you access `cached.get_record` you get a **new wrapper coroutine function**. That means:

- The cache is on self (decorator)
- The wrapper closes over `self._cache`
- But since the function is recreated on each attribute access, the cache is never persisted?

Actually `self._cache` is on the decorator instance, so should persist in the decorator.

So the problem is not that cache is on wrapper, but more subtle.

---

I suspect the problem is actually this: You are **decorating a coroutine method** with a decorator that returns a plain coroutine function wrapper, but your decorator is applied dynamically via `__getattr__`. The attribute `get_record` doesn't exist on the decorator instance, so every time you access `cached.get_record`, you get a NEW *wrapper coroutine function*. 

But the problem arises if your code (the caller of the decorator) does something like:

```python
v1 = await cached.get_record("a1")  # call 1
v2 = await cached.get_record("a1")  # call 2
```

Does `cached.get_record` return the same coroutine function object each time? No, a new wrapper coroutine function each time.

Is the cache updated? Yes, because cache is on self.

However, your `DummyHistorian().get_record` is an async method, so calling `cached.get_record("a1")` calls the wrapper `wrapper("a1")` which internally calls `target("a1")`.

But what about the **bound method** problem?

Is `target` properly bound? In `__getattr__`, you do:

```python
target = getattr(self._inner, name)
```

If `self._inner` is an instance, `target` is a method bound to `self._inner`.

So the call:

```python
value = await target(*args, **kwargs)
```

should be fine.

---

Another angle:

**The problem is that cache is not updated properly because each 'wrapper' function overwrites or fails to update the cache.**

But `_cache` is an `OrderedDict` on the decorator instance, so updating it should persist across calls.

---

One subtle potential problem: You are decorating an **async instance method**, but your decorator cache key includes `name`, normalized args and kwargs. If your `args` includes the `self` of the inner method (i.e. the bound method's `self`), maybe your cache key includes `self` or something unhashable that causes normalization to fail or create unique keys every time.

Check your cache key normalization:

```python
def _make_key(self, name: str, args: Tuple, kwargs: Dict) -> Hashable:
  # normalize args and kwargs recursively
```

If the `args` includes a reference to `self` (the inner instance), then `repr(self)` gets inserted as normalized fallback.

Because each time `self` is a different object or the repr string is unique (maybe includes memory address), the key will be unique and cache misses will happen every time.

So, depending on how the inner method is passed, your key construction includes the `self` instance.

---

**Most likely cause:**

When you call:

```python
v1 = await cached.get_record("a1")
```

the `args` to `wrapper` are `("a1",)`, but does the underlying target expect `self` as first argument?

No, because `target = getattr(self._inner, "get_record")` is a bound method of `self._inner`. So calling `target(*args)` passes just the arguments.

When you call the wrapper, you pass args = ("a1",), so key is:

```python
key = (name, normalized args, normalized kwargs)
```

where `name` = "get_record"

and `args` = ("a1",), no `self`.

So the key is always `"get_record", ("a1",), ()`

Thus, keys would be identical both times.

---

Why does the cache stay empty? Let's look at line 112:

```python
self._cache[key] = (expires_at, value)
```

If the cache has correct key, then after insertion length of cache should be 1.

But your debug output says cache state is 0 items after both calls.

This means:

- The cache insertion does not take effect.
- The cache dict is modified but when you examine it, it's empty.
- Maybe the decorator instance is replaced?

---

**Key insight:**

Your decorator class inherits from `HistorianDecorator`, which only defines:

```python
class HistorianDecorator:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, item):
        return getattr(self._inner, item)
```

But your subclass overrides `__getattr__`.

The problem is: **from the test code, is the `cached` instance ever referenced consistently?**

Another possible issue: are you sure you are using the exact same `cached` instance on both calls?

Because if the decorator is instantiated fresh per call, cache is empty fresh every time.

---

If that's ruled out, here is another very common subtle mistake with async cache decorators:

**Because your wrapper function is a new function returned by `__getattr__` every time, the coroutines are tricky.**

If in your test you do this:

```python
f1 = cached.get_record
r1 = await f1("a1")
f2 = cached.get_record
r2 = await f2("a1")
```

The cache works fine.

But if you do:

```python
r1 = await cached.get_record("a1")
r2 = await cached.get_record("a1")
```

then on each call, `cached.get_record` returns a fresh wrapper function.

But since `cached.get_record` is new each time, the `CACHE_HITS` label, etc, might not count properly.

But cache should still update.

---

**Very important to note:** In your class you call `self._locks: Dict[Hashable, asyncio.Lock] = {}`

The method `_get_lock(self, key)` inserts a lock in `self._locks`.

Are you sure the locks are the same across calls? If the decorator is single instance, yes.

---

**Hypothesis on what causes cache to be empty:**

Your decorator uses `__getattr__` dynamically to return a *new wrapper function* every time. But the caller uses a *bound method* style async call.

If instead the interface used explicit decorated methods (i.e. an attribute assigned once at `__init__`), the function would be consistent.

Due to this dynamic behavior, the cache insertion is being done, but

- The cache dictionary `self._cache` is being mutated.
- But if you do an external debugging print just after mutation (like `print(len(self._cache))`), it shows 1.
- But in your separate debug prints (from test harness), you see 0 items.
- This strongly suggests your test code looks at *a different decorator instance* than the one performing the cache updates.

---

### Summary:

- Your decorator class stores cache on instance (`self._cache`).
- Your `__getattr__` *builds and returns a new async wrapper function* for every attribute access.
- The inner method is correctly called and awaited.
- The key is consistent on repeated calls.
- But cache state you observe in test is always empty, so cache updates don't persist.
- The problem is most likely that you apply the decorator dynamically via `__getattr__`, so each time you access `cached.get_record`, you get a new wrapper function object.
- Your test probably calls `await cached.get_record("a1")` twice, **but behind the scenes this calls `__getattr__` twice, each returning a new function.** However, `self._cache` persists on the decorator.
- Since the cache dictionary is on the same decorator instance, cache miss should only happen once.

If cache stays empty, maybe you made a mistake: You shadowed `cached.get_record` by calling `cached.get_record()` (which calls the wrapper coroutine function)...

If you do:

```python
cached.get_record = cached.get_record
```

you override the dynamic behavior with the wrapper function, which might cause key bugs.

---

# Final Thought - Actual Bug:

From all the above analysis, the most likely bug is: **the cache key includes positional arguments including a mutable or unhashable argument, or includes `self` or something that changes each call, causing the key to be different every time, and this leads to cache misses and the cache appearing empty.**

### How to confirm:

Add debug prints inside `_make_key` to print the key generated.

Or print the keys inserted in `_cache`.

Example:

```python
def _make_key(self, name: str, args: Tuple, kwargs: Dict) -> Hashable:
    # ... existing code ...
    key = (name, tuple(normalize(a) for a in args), tuple(sorted((k, normalize(v)) for k, v in kwargs.items())))
    print(f"Cache key for {name}: {key!r}")
    return key
```

Then observe keys generated in your test.

---

### If `DummyHistorian.get_record` is an instance method, you might be passing `self` as the first positional argument by accident.

In your test code:

```python
v1 = await cached.get_record("a1")
```

`cached.get_record` (the wrapper) is called with args `("a1",)` but the inner `target` is `self._inner.get_record`, which is a bound method and expects just `"a1"` as argument.

Good.

---

### But if the interface is like:

```python
# Wrong call
v1 = await cached.get_record(inner, "a1")
```

then `args` includes `inner` as `self`, making key unique.

---

### You can try an experiment:

Change `_make_key` to ignore the `self` parameter if it's present.

Or make the decorator cache keys exclude the `self` argument of the method.

One way: skip the first argument in `args` (which is possibly `self`), only cache based on subsequent args.

---

# Recommendation:

Change `_make_key` as:

```python
def _make_key(self, name: str, args: Tuple, kwargs: Dict) -> Hashable:
    # If first arg is inner instance (self), skip it
    normalized_args = args
    if args:
        first_arg = args[0]
        if first_arg is self._inner:
            normalized_args = args[1:]
    def normalize(v):
       # ... existing
    norm_args = tuple(normalize(a) for a in normalized_args)
    norm_kwargs = tuple(sorted((k, normalize(v)) for k, v in kwargs.items()))
    return (name, norm_args, norm_kwargs)
```

This way, the cache key won't include the inner instance (self), so keys are stable.

---

# Summary:

**Your cache key includes the bound `self` or some mutable object in args, making keys unique every call, so cache misses always happen and cache stays "empty" for the requested key.**

Therefore, the cache insertions do happen but never found again because the keys differ.

Fix: Adjust `_make_key` to exclude `self._inner` if it is present as the first argument, so the cache key is consistent between calls.

---

If you want me, I can write a minimal fix patch for your decorator. Just ask!