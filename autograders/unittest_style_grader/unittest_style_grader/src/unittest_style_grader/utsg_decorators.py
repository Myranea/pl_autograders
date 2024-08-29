import dataclasses
import functools
from typing import Any, Callable, Concatenate, ParamSpec
from .utsg_testcase import UTSGTestCase, UTSGTestCaseInfo

P = ParamSpec('P')
UTSGTestCaseFun = Callable[Concatenate[UTSGTestCase, P], None]


# how to create the name decorator using a class
# class name:
#     def __init__(self, test_name: str):
#         self.test_name = test_name
#
#     def __call__(self, test_fun: UTSGTestCaseFun) -> UTSGTestCaseFun:
#         @functools.wraps(test_fun)
#         def wrapper(test_case: UTSGTestCase, *args: P.args, **kwargs: P.kwargs) -> None:
#             test_case.utsg_test_case_info.name = self.test_name
#             return test_fun(test_case, *args, **kwargs)
#
#         return wrapper

# how to create the name decorator using just a function instead
# def name(test_name: str) -> Callable[[UTSGTestCaseFun], UTSGTestCaseFun]:
#     def outer(test_fun: UTSGTestCaseFun) -> UTSGTestCaseFun:
#         @functools.wraps(test_fun)
#         def inner(self: UTSGTestCase, *args: P.args, **kwargs: P.kwargs) -> None:
#             self.utsg_test_case_info.name = test_name
#             return test_fun(self, *args, **kwargs)
#
#         return inner
#
#     return outer


class UTSGDecoratorFactory:
    """
    Create a decorator that can set the specified member of a :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>` to the specified value
    """

    def __init__(self, member_name: str, member_value: Any):
        """
        :param member_name: the name of the member in :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>` to modify
        :param member_value: The value to set :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>`.member_name to
        """
        self.member_name = member_name
        self.member_value = member_value

    def __call__(self, test_fun: UTSGTestCaseFun) -> UTSGTestCaseFun:
        """
        Create a wrapper function for test_fun that sets the test's :ref:`utsg_test_case_info <utsgTestCaseInfo>` ``.member_name = member_value`` \n
        :param test_fun: the test function to wrap
        :return: the wrapped function
        """

        @functools.wraps(test_fun)
        def wrapper(test_case: UTSGTestCase, *args: P.args, **kwargs: P.kwargs) -> None:
            setattr(test_case.utsg_test_case_info, self.member_name, self.member_value)
            return test_fun(test_case, *args, **kwargs)

        return wrapper


# create the decorators for each member of a UTSGTestCaseInfo that we want to be able to set using decorators
name = functools.partial(UTSGDecoratorFactory, 'name')
description = functools.partial(UTSGDecoratorFactory, 'description')
max_points = functools.partial(UTSGDecoratorFactory, 'max_points')
points_lost_on_failure = functools.partial(UTSGDecoratorFactory, 'points_lost_on_failure')
include_in_results = functools.partial(UTSGDecoratorFactory, 'include_in_results')
hidden = functools.partial(UTSGDecoratorFactory, 'hidden')

# setting the points earned in the test case does not make sense
# points = functools.partial(utsg_decorator_factory, 'points')

# these can be set using decorators but I don't think make sense to set using it
message = functools.partial(UTSGDecoratorFactory, 'message')
output = functools.partial(UTSGDecoratorFactory, 'output')
images = functools.partial(UTSGDecoratorFactory, 'images')

# the status of the test case should not be allowed to be set at all outside of the testing framework
# status = functools.partial(utsg_decorator_factory, '_status')

# The below bit of code creates a decorator for every member found in UTSGTestCase Info
# but I think it is too confusing/non standard to do even if it is shorter, less error prone, and
# "automatically updates" which decorators are available based on changes in UTSGTestCase
# current_name_space = globals()
# for member in dataclasses.fields(UTSGTestCaseInfo):
#     current_name_space[member.name] = functools.partial(utsg_decorator_factory, member.name)
