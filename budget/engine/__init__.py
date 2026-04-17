"""Grass & Goat Global forecast engine.

Pure-function architecture: every module takes an immutable Assumptions object
and returns pandas/numpy structures. No file I/O. No global state. No side
effects. This is what makes v2 sensitivity sweeps cheap.
"""
