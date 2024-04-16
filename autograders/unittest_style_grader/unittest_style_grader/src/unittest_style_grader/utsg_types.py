"""
Collection of type aliases used throughout the unittest style grader
"""

from typing import TypedDict
import enum
import os


class PrairieLearnImage(TypedDict):
    """
    How PrairieLearn specifies images to give back from the external grading results. \n
    """
    label: str
    url: str


class PrairieLearnTestCaseJsonDictOptional(TypedDict, total=False):
    """
    The optional values for a test case reported back to PrairieLearn in dictionary form
    that is ready to be processed by the json library.

    """
    description: str
    message: str
    output: str
    images: list[PrairieLearnImage]


class PrairieLearnTestCaseJsonDict(PrairieLearnTestCaseJsonDictOptional):
    """
    Add in the "required" values for a test case reported back to PrairieLearn in dictionary form
    that is ready to be processed by the json library. Not technically required by PrairieLearn but I
    require that they be reported back.
    This is making use of https://docs.python.org/3/library/typing.html#typing.TypedDict.__optional_keys__
    to specify what keys are required in the dictionary and what keys might appear
    """
    name: str
    max_points: float
    points: float


class UTSGTestStatus(enum.Enum):
    PASSED = 'Passed'
    FAILED = 'Failed'
    CRASHED = 'Crashed'
    RUNNING = 'Running'
    SCHEDULED = 'Scheduled'

pathlike = str | bytes | os.PathLike
class AccessControls(TypedDict, total=False):
    r: list[pathlike]
    w: list[pathlike]
    x: list[pathlike]

    # read and write
    rw: list[pathlike]
    wr: list[pathlike]

    # read and execute
    rx: list[pathlike]
    xr: list[pathlike]

    # write and execute
    wx: list[pathlike]
    xw: list[pathlike]

    # read, write, and execute
    rwx: list[pathlike]
    rxw: list[pathlike]
    wrx: list[pathlike]
    wxr: list[pathlike]
    xrw: list[pathlike]
    xwr: list[pathlike]
