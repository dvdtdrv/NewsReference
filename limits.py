"""
A hard time limit for one web request (added 9 Nov 2026).

`requests` only limits how long it waits for EACH piece of an answer, not the whole answer.
A site that answers very slowly, or a connection that gets stuck half-way, can therefore hold
a run for many minutes - on 9 Nov 2026 one stuck photo page made every GitHub run hit its
20-minute limit, so the site stopped updating for hours.

`within(seconds, fn, ...)` runs fn in a background thread and gives up after `seconds`:
it raises requests.Timeout, which the callers already treat as "couldn't reach the site".
The stuck thread is a daemon thread, so it never keeps the program from finishing.
"""

import threading

import requests


def within(seconds, fn, *args, **kwargs):
    result = {}

    def run():
        try:
            result["value"] = fn(*args, **kwargs)
        except BaseException as e:          # hand any error back to the caller
            result["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise requests.Timeout(f"gave up after {seconds} s")
    if "error" in result:
        raise result["error"]
    return result.get("value")
