"""Deterministic file helpers for tests; every handle closes before return."""
from __future__ import annotations


def read_file(path, mode="r", encoding=None, errors=None, size=-1):
    kwargs = {}
    if "b" not in mode:
        if encoding is not None:
            kwargs["encoding"] = encoding
        if errors is not None:
            kwargs["errors"] = errors
    with open(path, mode, **kwargs) as stream:
        return stream.read(size)


def write_file(path, data, mode="w", encoding=None, errors=None):
    kwargs = {}
    if "b" not in mode:
        if encoding is not None:
            kwargs["encoding"] = encoding
        if errors is not None:
            kwargs["errors"] = errors
    with open(path, mode, **kwargs) as stream:
        return stream.write(data)
