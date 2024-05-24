import copy
import dataclasses
import jinja2
import json
import os
import traceback
import unittest
from typing import TextIO, Type
from types import TracebackType
from .utsg_types import PrairieLearnImage, UTSGTestStatus
from .utsg_testcase import UTSGTestCaseInfo, UTSGTestCase, UngradableError

SysExceptionType = tuple[Type[BaseException], BaseException, TracebackType] | tuple[None, None, None]


@dataclasses.dataclass
class UTSGRunSummary:
    tests: list[UTSGTestCaseInfo]
    num_tests_available: int = dataclasses.field(default=0, init=False)
    num_tests_ran: int = dataclasses.field(default=0, init=False)
    num_tests_passed: int = dataclasses.field(default=0, init=False)
    num_tests_failed: int = dataclasses.field(default=0, init=False)
    points_available: float = dataclasses.field(default=0.0, init=False)
    points_earned: float = dataclasses.field(default=0.0, init=False)

    def __post_init__(self):
        completed = {UTSGTestStatus.PASSED, UTSGTestStatus.FAILED}
        ran = completed | {UTSGTestStatus.CRASHED}
        for test in self.tests:
            self.num_tests_available += 1
            self.points_available += test.max_points
            if test._status in ran:
                self.num_tests_ran += 1
            if test._status in completed:
                self.points_earned += test.points
            if test._status == UTSGTestStatus.PASSED:
                self.num_tests_passed += 1
            elif test._status == UTSGTestStatus.FAILED:
                self.num_tests_failed += 1

    def __add__(self, other: 'UTSGRunSummary') -> 'UTSGRunSummary':
        total = copy.copy(self)
        total.tests.extend(other.tests)
        total.num_tests_available += other.num_tests_available
        total.num_tests_ran += other.num_tests_ran
        total.num_tests_passed += other.num_tests_passed
        total.num_tests_failed += other.num_tests_failed
        total.points_available += other.points_available
        total.points_earned += other.points_earned
        return total


class UTSGTestResult(unittest.TestResult):
    def __init__(self,
                 # arguments inherited from unittest.TestResult
                 stream: TextIO | None = None, descriptions: bool | None = None, verbosity: int | None = None,
                 result_location: str | None = None) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.utsg_results = dict()  # the results of the test
        self._utsg_score_floor = 0.0
        self._utsg_score_ceiling = 1.0

        self.visible_tests_info: list[UTSGTestCaseInfo] = []  # information about all the visible tests
        self.hidden_tests_info: list[UTSGTestCaseInfo] = []  # information about only the hidden tests
        self.excluded_tests_info: list[UTSGTestCaseInfo] = []  # information about the excluded tests

        self._tester_crashed = False
        self.scored = False  # whether this assignment has been scored or not

        if result_location is not None:
            self.utsg_result_location = result_location
        else:
            self.utsg_result_location = UTSGTestCase.results_dir / 'results.json'
    # TODO: Refactor these properties. Maybe keep the necessary ones but add a method called info or something that handles
    # other information about the test.
    @property
    def utsg_score_floor(self) -> float:
        """
        A students score cannot drop below this value.
        Must be a  value between [0.0, 1.0]
        """
        return self._utsg_score_floor

    @utsg_score_floor.setter
    def utsg_score_floor(self, score_floor: float):
        """
        A students score cannot drop below this value.
        Must be a  value between [0.0, 1.0]
        """
        set_message = f'Attempted to set score floor to {score_floor}.\n'
        if score_floor < 0.0:
            raise UngradableError(f'{set_message}The score floor cannot be set below 0.0')
        elif score_floor > 1.0:
            raise UngradableError(f'{set_message}The score floor cannot be set above 1.0')
        else:
            self._utsg_score_floor = score_floor

    @property
    def utsg_score_ceiling(self) -> float:
        """
        A students score cannot go above this value.
        Must be a  value between [0.0, 1.0]
        """
        return self._utsg_score_ceiling

    @utsg_score_ceiling.setter
    def utsg_score_ceiling(self, score_ceiling: float) -> None:
        set_message = f'Attempted to set score floor to {score_ceiling}.\n'
        if score_ceiling < 0.0:
            raise UngradableError(f'{set_message}The score floor cannot be set below 0.0')
        elif score_ceiling > 1.0:
            raise UngradableError(f'{set_message}The score floor cannot be set above 1.0')
        else:
            self._utsg_score_ceiling = score_ceiling

    @property
    def gradable(self) -> bool:
        if 'gradable' not in self.utsg_results:
            self.utsg_results['gradable'] = True
        return self.utsg_results['gradable']

    @gradable.setter
    def gradable(self, new_value: bool) -> None:
        self.utsg_results['gradable'] = new_value

    @property
    def images(self) -> list[PrairieLearnImage]:
        if 'images' not in self.utsg_results:
            self.utsg_results['images'] = []
        return self.utsg_results['images']

    @images.setter
    def images(self, new_value: list[PrairieLearnImage]) -> None:
        self.utsg_results['images'] = new_value

    @property
    def message(self) -> str | None:
        return self.utsg_results.get('message', None)

    @message.setter
    def message(self, new_value: str) -> None:
        if new_value is not None:
            self.utsg_results['message'] = new_value

    @property
    def output(self) -> str | None:
        return self.utsg_results.get('output', None)

    @output.setter
    def output(self, new_value: str) -> None:
        if new_value is not None:
            self.utsg_results['output'] = new_value

    @property
    def score(self) -> float:
        if 'score' not in self.utsg_results:
            self.utsg_results['score'] = 0.0
        return self.utsg_results['score']

    @score.setter
    def score(self, new_value: float) -> None:
        self.utsg_results['score'] = new_value

    @property
    def recorded_tests(self) -> list:
        if 'tests' not in self.utsg_results:
            self.utsg_results['tests'] = []
        return self.utsg_results['tests']

    @recorded_tests.setter
    def recorded_tests(self, new_value: list) -> None:
        self.utsg_results['tests'] = new_value

    def _log_test_result(self, test: UTSGTestCaseInfo) -> None:
        """
        Put the results of the test into the results dictionary that will be written to the JSON file
        on test completion
        :param test: The completed test case whose results we should add to the JSON file
        :return: None
        """
        if not test.include_in_results:
            self.excluded_tests_info.append(test)
        elif test.hidden:
            self.hidden_tests_info.append(test)
        else:
            self.visible_tests_info.append(test)

    def startTestRun(self) -> None:
        """
        When starting a new set of tests clear out the results of old test runs
        :return:
        """
        # NOTE: utsg_results is how the json is created. 
        super().startTestRun()
        self.utsg_results = {
            'gradable': True,
            'score': 0.0,
            'tests': []
        }

    def stopTestRun(self) -> None:
        """
        Write the results of the tests out to the JSON file
        :return:
        """
        # TODO need to check if we completed successfully or not before scoring
        super().stopTestRun()
        if self.utsg_score_floor > self.utsg_score_ceiling:
            raise UngradableError(
                f'score floor set above score score ceiling. {self.utsg_score_floor} > {self.utsg_score_ceiling}')

        hidden_results = UTSGRunSummary(self.hidden_tests_info)
        visible_results = UTSGRunSummary(self.visible_tests_info)
        total_results = hidden_results + visible_results

        # score is a percent and also not allowed to drop below 0
        if not self.scored:
            self.score = (total_results.points_earned / total_results.points_available
                          if total_results.points_available > 0.0 else 0.0)
            self.score = max(self.utsg_score_floor, self.score)
            self.score = min(self.utsg_score_ceiling, self.score)
            self.scored = True

        # put the results of the visible tests in the json to be given back to PrairieLearn
        self.recorded_tests = [test.as_prairielearn_json_dict() for test in self.visible_tests_info]

        template_environment = jinja2.Environment(loader=jinja2.PackageLoader('unittest_style_grader'),
                                                  autoescape=jinja2.select_autoescape())
        final_results_template = template_environment.get_template('final_results.jinja.txt')
        final_results = final_results_template.render(hidden_results=hidden_results,
                                                      visible_results=visible_results,
                                                      total_results=total_results,
                                                      score=self.score * 100.0)
        # TODO: Is this line necessary?
        self.message = final_results + self.message if self.message is not None else ''

        with open(self.utsg_result_location, 'w') as result_json:
            json.dump(self.utsg_results, result_json, indent=2)

    def startTest(self, test: UTSGTestCase) -> None:
        self.utsg_score_floor = test.utsg_score_floor
        self.utsg_score_ceiling = test.utsg_score_ceiling
        test.utsg_test_case_info._status = UTSGTestStatus.RUNNING
        super().startTest(test)

    def stopTest(self, test: UTSGTestCase) -> None:
        super().stopTest(test)
        # TODO: Change the behavior where stopTest checks for the image, message, and output attributes
        # if there are any top level attributes in the test class, copy them over
        if test.images:
            self.images = test.images
        if test.message:
            self.message = test.message
        if test.output:
            self.output = test.output

        for utsg_subtest in test.utsg_subtests:
            if utsg_subtest.utsg_test_case_info._status == UTSGTestStatus.CRASHED:
                print(f'{utsg_subtest.utsg_test_case_info.name} crashed')

            if utsg_subtest.utsg_test_case_info._status == UTSGTestStatus.PASSED:
                self._log_success(utsg_subtest.utsg_test_case_info)
            elif utsg_subtest.utsg_test_case_info._status in (UTSGTestStatus.FAILED, UTSGTestStatus.CRASHED):
                self._log_failure(utsg_subtest.utsg_test_case_info)
            else:
                print(f'{test.utsg_test_case_info.name} completed before its subtest'
                      f' {utsg_subtest.utsg_test_case_info.name} finished running.')

        if test.utsg_test_case_info._status == UTSGTestStatus.RUNNING:
            # We are assuming that if a test case reaches the end and was never marked as having explicitly failed
            # then it passed the test. As far as I know this should only happen if the test case uses subtests
            # and all subtests passed
            self._log_success(test.utsg_test_case_info)

    def addError(self, test: UTSGTestCase, err: SysExceptionType) -> None:
        """
        An exception was raised inside a test but not handled
        :param test:
        :param err:
        :return:
        """
        super().addError(test, err)
        exception_type, exception, tb = err
        # TODO make an exception for the end grading error
        self.gradable = False
        self.score = 0.0
        self.scored = True

        crash_template = '{name} CRASHED for the following reason\n{reason}{extra_info}'
        extra_info = ''
        if isinstance(exception, UngradableError):
            reason = exception.message
        else:
            reason = f'An error of type {exception_type} occurred when testing.\n' \
                     f'Exception Value: {exception}\n' \
                     f'Trace Back: {traceback.format_tb(tb)}\n'

        # TODO why am I having to check this? Is it actually needed?
        # If it wasn't necessary I wouldn't have done it but I don't remember why
        # so I need to find out and add a better comment explaining why past Matthew wrote this check
        # currently one reason is that this method is called when an exception is triggered in setupClass
        # and setUpClass is not a  UTSGTestCase
        if hasattr(test, 'utsg_test_case_info'):
            test.utsg_test_case_info._status = UTSGTestStatus.CRASHED
            # assume that since this is the test where the exception was raised, it is the culprit of the crash
            crashed_test_info = test.utsg_test_case_info
            for subtest in test.utsg_subtests:  # but check the subtests because they could have caused it
                # if it is a subtest that crashed it is the actual culprit, and we should use its information
                # in reporting things
                if subtest.utsg_test_case_info._status == UTSGTestStatus.CRASHED:
                    crashed_test_info = subtest.utsg_test_case_info
                    break
            if crashed_test_info.output:
                extra_info = f'\n\n--------Original Output--------\n' \
                             f'{crashed_test_info.output}'

            crashed_test_info.output = crash_template.format(name='This test',
                                                             reason=reason, extra_info=extra_info)
            if self.output:
                extra_info = f'\n\n--------Original Output--------\n' \
                             f'{self.output}'
            else:
                extra_info = ''
            self.output = crash_template.format(name=crashed_test_info.name,
                                                reason=reason,
                                                extra_info=extra_info)
        else:
            extra_info = ''
            if self.output:
                extra_info = f'\n\n--------Original Output--------\n' \
                             f'{self.output}'
            self.output = crash_template.format(name='', reason=reason, extra_info=extra_info)

        # TODO adding an error to the test should mark the overall tester as having crashed
        # but should it really? not so sure
        # self._tester_crashed = True
        self.stop()  # stop any further testing

    def addFailure(self, test: UTSGTestCase, err: SysExceptionType) -> None:
        super().addFailure(test, err)
        self._log_failure(test.utsg_test_case_info)

    def _log_failure(self, test: UTSGTestCaseInfo) -> None:
        # TODO: Refactor such that the message is created without checking test.message
        test._status = UTSGTestStatus.FAILED
        if test.points is None:
            test.points = -test.points_lost_on_failure
        if test.message is None:
            test.message = f'Failed {test.name}'

        self._log_test_result(test)

    def addSuccess(self, test: UTSGTestCase) -> None:
        super().addSuccess(test)
        self._log_success(test.utsg_test_case_info)

    def _log_success(self, test: UTSGTestCaseInfo) -> None:
        # TODO: Ask Butner if the Passed message is necessary here.
        test._status = UTSGTestStatus.PASSED
        if test.points is None:
            test.points = test.max_points
        if test.message is None:
            test.message = f'Passed {test.name}'

        self._log_test_result(test)

    def addExpectedFailure(self, test: UTSGTestCase, err: SysExceptionType) -> None:
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test: UTSGTestCase) -> None:
        # TODO: possibly need to change how message is assigned to UTSGTestResult.
        self.gradable = False
        self.message = f'{test.utsg_test_case_info.name} passed when it was marked as expecting to fail.'
        super().addUnexpectedSuccess(test)
        self.stop()

    def addSubTest(self, test: UTSGTestCase, subtest: unittest.case.TestCase,
                   err: SysExceptionType | None) -> None:
        super().addSubTest(test, subtest, err)
        if err is not None:
            if test.utsg_test_case_info._status != UTSGTestStatus.FAILED:
                self._log_failure(test.utsg_test_case_info)
