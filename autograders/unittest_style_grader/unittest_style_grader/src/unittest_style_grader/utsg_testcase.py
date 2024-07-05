from contextlib import AbstractContextManager
import dataclasses
import functools
import json
import multimethod
import os
import pathlib
import shlex
import subprocess
import traceback
from types import TracebackType
from typing import Any, Optional, Type
import unittest
import warnings
import tempfile

from utsg_types import AccessControls, PrairieLearnImage, PrairieLearnTestCaseJsonDict, UTSGTestStatus
from utsg_util import are_strs_equal_ignoring_whitespace


class UngradableError(Exception):

    def __init__(self, message: str = 'Your submission is ungradable for some reason.\n'
                                      'Ask your instructor to update their test cases to provide you '
                                      'a better explanation for what went wrong', *args: object) -> None:
        super().__init__(*args)
        self.message = message


@dataclasses.dataclass
class UTSGTestCaseInfo:
    """
    The information about a ``TestCase`` to report back to PrairieLearn

    **Values Describing The Test**
    
    :var name: The name of the test case. \n
      **Default:** ``"Unnamed Test"`` \n
      **Inherited by Subtests?** Partial. The name of the subtest will be ``f'{name} subtest {i}'`` where ``i`` is the ith subtest
      run and ``i`` starts at 1.
    :var description: A string describing what this test case does. \n
      **Default:** ``None``\n 
      If not specified, no description for the test is given back to PrairieLearn. \n
      **Inherited by Subtests?** True. Subtests will use the same description as their parent test if not overridden.
    :var max_points: How many points this test is worth. \n
      **Default:** ``1.0`` \n
      **Inherited by Subtests?** True. ``max_points`` for each subtest will be equal to their parent's ``max_points``
    :var points_lost_on_failure: how many points are lost if this test fails. \n
      **Default:** ``0.0`` \n
      **Inherited by Subtests?** True. ``points_lost_on_failure`` for each subtest will be equal to their parent's ``points_lost_on_failure``
    :var include_in_results: whether or not the results of this test case should be reported back to PrairieLearn.
      If False the test case is still run but nothing about this test will be used to calculate a student's score
      or be reported back to PrairieLearn \n
      **Default:** ``True`` \n
      **Inherited by Subtests?** False. The most common reason to set this to be ``True`` is if a test is just serving as
      a container for multiple subtests and only the results of the subtests should be reported back
    :var hidden: whether or not the existence of this test should be revealed to the student. If ``True`` nothing about
      this test is reported back to PrarieLearn, and therefore, the student but unlike setting ``include_in_results = False``
      the points earned on this test will be used to calculate a student's score and the student will be informed of
      the number of hidden tests they passed, how many hidden tests there are, and how many points from the hidden
      test they earned \n
      **Default:** ``False`` \n
      Inherited by Subtests? True. ``hidden`` for each subtest will be equal to their parent's ``hidden``

    **Values generated during a test**
    
    :var points: How many points a student earned on the test. \n
      **Default:** ``None`` \n
      If not set explicitly during the test will be ``max_points`` if the test passes and
      ``points_lost_on_failure`` if the test fails. If it is set during the test, it will be whatever value was set \n
      **Inherited by Subtests?** False
    :var msg: A string containing any additional information you want to show the student \n
        **Default:** ``None`` \n
        If not specified, no description for the test is given back to PrairieLearn. \n
        **Inherited by Subtests?:** False
    :var output: Any output produced by running the students code that you wish to show them \n
        **Default:** ``None`` \n
        If not specified, no output for the test is given back to PrairieLearn. \n
        **Inherited by Subtests?:** False
    :var images: Any images produced during the test you wish to display to the student \n
      **Default:** An empty list. If not specified, no images for the test are given back to PrairieLearn.
    """

    # descriptive information about the test
    # TODO: max points, points on failure, points, hidden are required.
    # TODO: include_in_results may be deprecated
    name: str = 'Unnamed Test'
    description: Optional[str] = None
    max_points: float = 1.0
    points_lost_on_failure: float = 0.0
    include_in_results: bool = True
    hidden: bool = False

    # generated during running the test
    # TODO: These things should be organized under an attribute called info or something
    points: Optional[float] = dataclasses.field(default=None, init=False)
    message: Optional[str] = dataclasses.field(default=None, init=False)
    output: Optional[str] = dataclasses.field(default=None, init=False)
    images: list[PrairieLearnImage] = dataclasses.field(default_factory=list, init=False)  # default is the empty list
    _status: UTSGTestStatus = dataclasses.field(default=UTSGTestStatus.SCHEDULED, init=False)

    def as_prairielearn_json_dict(self) -> PrairieLearnTestCaseJsonDict:
        """
        Create a dictionary that can be used in the Prairie Learn results JSON for a test case \n
        Discards any of the optional parameters that aren't set
        """
        return {attr_name: attr_value for attr_name, attr_value in dataclasses.asdict(self).items() if
                attr_name in PrairieLearnTestCaseJsonDict.__required_keys__ or
                attr_name in PrairieLearnTestCaseJsonDict.__optional_keys__ and attr_value}


class UTSGTestCase(unittest.TestCase):
    """
    Logical test unit of the grader, inherits from `unittest.TestCase <https://docs.python.org/3/library/unittest.html#unittest.TestCase>`_ \n
    **Values Generated During a Subtest**

    :var utsg_score_floor: Minimum score the subtest returns. \n**Default:** ``0.0``
    :var utsg_score_celing: Maximum score the subtest returns. \n**Default:** ``1.0``
    :var message: A string containing additional information you want to show to the student. \n**Default:** ``None``
    :var output: Any output produced by running the students code that you wish to show them \n
        **Default:** ``None`` \n
    :var images: Any images produced during the test you wish to display to the student \n
      **Default:** An empty list. If not specified, no images for the test are given back to PrairieLearn.\n

    **Directory Paths**
    The default locations for where things are currently in PrairieLearn
    :var grade_dir: defaults to PL's path to the grade directory, otherwise defaults to /grade
    :var data_dir:
    :var data: Dictionary representing the `data.json <https://prairielearn.readthedocs.io/en/latest/question/#question-data-storage>`_ for PrairieLearn. Defaults to empty dictionary. 
    setUpClass attempts to assign this value to the `data.json <https://prairielearn.readthedocs.io/en/latest/question/#question-data-storage>`_ file.
    .. note:: TODO please finish this
    """
    utsg_score_floor = 0.0
    utsg_score_ceiling = 1.0
    # TODO: Combine these under an info attribute
    message: Optional[str] = None
    output: Optional[str] = None
    images: list[str] = []
    data = {}

    # the default locations for where things are currently at in Prarie Learn
    grade_dir = pathlib.Path('/grade' if 'GRADE_DIR' not in os.environ else os.environ['GRADE_DIR'])
    temp_dir = tempfile.TemporaryDirectory()
    print(temp_dir)
    plDirs = os.listdir(grade_dir)
    for f in plDirs:
        src_path = os.path.join(grade_dir, f)
        dst_path = os.path.join(temp_dir.name, f)
        os.rename(src_path, dst_path)
    grade_dir = pathlib.Path(temp_dir.name)
    data_dir = grade_dir / 'data'
    results_dir = grade_dir / 'results'
    student_dir = grade_dir / 'student'
    tests_dir = grade_dir / 'tests'

    def __init__(self, methodName: str = 'runTest', description: Optional[str] = None,
                 max_points: float = 1.0, points_lost_on_failure: float = 0.0,
                 include_in_results: bool = True, hidden: bool = False):
        """
        See :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>` for the meaning of each parameter \n
        :param methodName: The name of the test case. The same as name in :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>`
        :param description: A string describing what this test case does
        :param max_points: How many points this test is worth
        :param points_lost_on_failure: how many points are lost if this test fails
        :param include_in_results: whether or not the results of this test case should be included
        :param hidden: whether or not the output, name, message, etc should be hidden from students or not
        """
        super().__init__(methodName)
        self.utsg_test_case_info = UTSGTestCaseInfo(methodName, description,
                                                    max_points, points_lost_on_failure,
                                                    include_in_results, hidden)
        self.utsg_subtests: list[UTSGSubTest] = []
    def __del__(self):
        plDirs = os.listdir(self.grade_dir)
        for f in plDirs:
            src_path = os.path.join(self.temp_dir.name, f)
            dest_path = os.path.join(pathlib.Path('/grade' if 'GRADE_DIR' not in os.environ else os.environ['GRADE_DIR']), f)
            os.rename(src_path, dest_path)
        os.rmdir(self.temp_dir.name)
    @classmethod
    def setUpClass(cls) -> None:
        """
        `classmethod <https://docs.python.org/3/library/functions.html#classmethod>`_ called before any test cases are ran. Resets the `UTSGTestCase.utsg_score_floor` to ``0.0`` and 
        ``UTSGTestCase.utsg_score_ceiling`` to ``1.0``, sets ``UTSGTestCase.message`` and ``UTSGTestCase.output`` to ``None``.
        Attempts to assign ``UTSGTestCase.data`` with the path to the PL `data.json <https://prairielearn.readthedocs.io/en/latest/question/#question-data-storage>`_ file. Removes student files' (including files created during the test)
        permissions for everything within the grade and results directory, but assigns student files' full permissions
        for files inside the student directory.
        """
        super().setUpClass()
        # (re)set back to defaults
        cls.utsg_score_floor = 0.0
        cls.utsg_score_ceiling = 1.0
        # TODO: Should message and output be under one attribute or should they stay separate?
        cls.message = None
        cls.output = None
        cls.data = {}

        try:
            with open(cls.data_dir / 'data.json') as data_file:
                cls.data = json.load(data_file)
        except FileNotFoundError:
            warnings.warn(f'Could not find data file at {cls.data_dir / "data.json"}. No data loaded.\n'
                          'If you were not making use of self.data in your tests you may safely ignore this warning.\n')

        # remove student permissions from everything within the grade and results directory
        # and make it so that any new files created there they have no permissions for
        # cls.run_program(args=['setfacl',
        #                       '-Rm', 'u:sbuser:-,default:u:sbuser:-,o::-,default:o::-',
        #                       str(cls.grade_dir), str(cls.results_dir)
        #                       # '-Rm', 'default:u:sbuser:-', str(cls.grade_dir),
        #                       # '-Rm', 'u:sbuser:-default:u:sbuser:-,', str(cls.results_dir),
        #                       # '-Rm', 'default:u:sbuser:-', str(cls.results_dir)
        #                       ],
        #                 )
        #sbuser refers to student
        cls.run_program(args=['chmod', '-R', '711', str(cls.grade_dir), str(cls.results_dir)])

        # except for what is in the student directory where they have full permissions
        # cls.run_program(args=['setfacl',
        #                       '-Rm', 'u:sbuser:rwx,default:u:sbuser:rwx,g:sbuser:rwx,default:g:sbuser:rwx',
        #                       str(cls.student_dir),
        #                      # '-Rm', 'default:u:sbuser:rwx', str(cls.student_dir),
        #                      # '-Rm', 'g:sbuser:rwx', str(cls.student_dir),
        #                      # '-Rm', 'default:g:sbuser:rwx', str(cls.student_dir)
        #                       ])
        cls.run_program(args=['chown', '-R', 'sbuser:sbuser', str(cls.student_dir)])
        cls.run_program(args=['chmod', '-R', '777', str(cls.student_dir)])

        # msg is missing as an explicit optional argument here
        # because how unittest.TestCase.subTest's default value for
        # msg is implementation dependent (it's unittest.case._subtest_msg_sentinel in python 3.10).
        # by not listing it as an explict optional argument we avoid creating the dependency on this implementation detail

    def add_graded_subTest(self, name: Optional[str] = None, description: Optional[str] = None,
                           max_points: Optional[float] = None, points_lost_on_failure: Optional[float] = None,
                           include_in_results: bool = True, hidden: Optional[bool] = None,
                           include_params_in_description: bool = True,
                           **params: Any) -> AbstractContextManager['UTSGSubTest']:
        """
        Create an independent test within in this test whose results will be reported back to PrairieLearn. The subtests
        created behave nearly identically to those created by `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_ except that if an ``Exception`` other than
        an `AssertionError <https://docs.python.org/3/library/exceptions.html#AssertionError>`_ is raised it will end the entire testing process and mark the submission as ``Ungradable`` \n
        :param name: The name of this subtest. If not specified it will be ``f'{ParentTest.name} subtest {i}'`` where
          ``i`` starts at ``1`` 
        :param description: The description of this subtest. If not specified it will be the parent test's description
        :param max_points: The maximum number of points available for this subtest.
          If not specified it will be the parent test's ``max_points``.
        :param points_lost_on_failure: The number of points lost if this subtest fails.
          If not specified it will be the parent test's ``points_lost_on_failure``
        :param include_in_results: Whether or not to include this test case's results when calculating the
          final grade and reporting back to PrairieLearn. If not specified it will default to ``True``
        :param hidden: Whether or not to hide this subtests results from the student.
          If not specified it will be the parent test's ``hidden``
        :param include_params_in_description: If true any additional parameter's will be appended to the end of the
          subtest's description
        :param params: Any additional values to display. The same as `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_
        :return: a :ref:`UTSGSubtest <utsgSubTest>`. Like :ref:`UTSGSubTest <utsgSubTest>` it has an :py:func:`utsg_test_case_info <utsg_testcase.UTSGSubTest.__init__>` member that you can access to set/modify
          the values that will be reported back to PrairieLearn
        """

        subtest_test_case_info = UTSGTestCaseInfo(
            name=name if name is not None else f'{self.utsg_test_case_info.name} subtest {len(self.utsg_subtests) + 1}',
            description=description if description is not None else self.utsg_test_case_info.description,
            max_points=max_points if max_points is not None else self.utsg_test_case_info.max_points,
            points_lost_on_failure=(points_lost_on_failure if points_lost_on_failure is not None else
                                    self.utsg_test_case_info.points_lost_on_failure),
            include_in_results=include_in_results,
            hidden=hidden if hidden is not None else self.utsg_test_case_info.hidden
        )

        if include_params_in_description:
            param_description = '  \n'.join([f'{param_name} = {param_value}'
                                             for param_name, param_value in params.items() if param_name != 'msg'])
            if subtest_test_case_info.description is None:
                subtest_test_case_info.description = ''
            subtest_test_case_info.description += '\n' + param_description

        subtest = UTSGSubTest(self, subtest_test_case_info, **params)
        self.utsg_subtests.append(subtest)
        return subtest

    # helper methods for running and testing programs
    @staticmethod
    def run_program(*args, **kwargs) -> subprocess.CompletedProcess:
        """
        Does `subprocess.run(*args, **kwargs) <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_ but captures any errors raised and transforms them into
        UngradableError. This is useful for when you need to run a program as the instructor and it must work \n
        :param args: positional args to forward to subprocess.run
        :param kwargs: keyword arguments to forward to subprocess.run
        :return: the result of running the program
        :raises: ``UngradableError`` if anything goes wrong in running the subprocess
        """
        try:
            return subprocess.run(*args, **kwargs)
        except Exception:
            raise UngradableError(
                f'Something went wrong when running the instructors code.\n'
                f'This did not cost you a submission.\n'
                f'Please report this error and include the following:\n'
                f' {traceback.format_exc()}')

    @staticmethod
    def run_as_student(*subprocess_run_pos_args, files_accessible: Optional[AccessControls] = None,
                       **subprocess_run_keyword_args) -> subprocess.CompletedProcess:
        """
        Run the program as a student \n
        :param subprocess_run_pos_args: positional arguments to forward to `subprocess.run <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_
        :param files_accessible: Additional files and directories accessible to the student. By default
          students have access to everything under ``cls.student`` (/grade/student)
        :param subprocess_run_keyword_args: keyword arguments to forward to `subprocess.run <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_
        :return: the completed results
        """
        if files_accessible is not None:
            # TODO check for duplicate entries and raise an exception
            for perms, files in files_accessible.items():
                # TODO setfacl may not work inside directories mounted inside the docker container
                subprocess.run(['setfacl', '-mR', f'u:sbuser:{perms}'] + list(files))

        # make us run as the student
        subprocess_run_keyword_args['user'] = 'sbuser'
        subprocess_run_keyword_args['group'] = 'sbuser'
        return subprocess.run(*subprocess_run_pos_args, **subprocess_run_keyword_args)

    def run_under_test_as_student(self, test_info: Optional[UTSGTestCaseInfo] = None,
                                  these_exceptions_makes_ungradable: type | tuple[type, ...] = (),
                                  expected_output: Optional[str | bytes] = None,
                                  expected_err: Optional[str | bytes] = None,
                                  expected_return_code: Optional[int] = None, enforce_whitespace: bool = False,
                                  files_accessible: Optional[AccessControls] = None,
                                  **subprocess_run_keyword_args) -> subprocess.CompletedProcess:
        """
        Do `subprocess.run(**subprocess_run_keyword_args) <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_ as the student user,
        checking the results against the expected values. Expected values are only checked if
        ``test_info`` is supplied and the results of the test are then stored there.
        If ``test_info`` is supplied and a mismatch in any of the expected vs produced values occurs,
        the test is marked as a failure.

        :param these_exceptions_makes_ungradable: a tuple of ``Exception`` types that if
          they occur while running the students program should mark the submission as ungradable
        :param test_info: The :ref:`UTSGTestCaseInfo <utsgTestCaseInfo>` to store the results of the test in. Expected values are only checked
          if this is provided. If provided, will also mark the test as failed if a mismatch occurs between any of the
          expected values and the values produced from running the student's code
        :param expected_output: What the expected output should be. If not given, it won't be checked
        :param expected_err: What the expected error output should be. If not given, it won't be checked
        :param expected_return_code: What the expected return code should be. If not given it won't be checked
        :param enforce_whitespace: Whether whitespace should be checked or not
        :param files_accessible: What files and directories the student should have access to while the test is running.
          By default, they only have access to /grade/student and what is in it
        :param subprocess_run__keyword_args: values to pass to `subprocess.run <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_
        :return: The CompletedProcess returned by doing `subprocess.run(**subprocess_run_args) <https://docs.python.org/3/library/subprocess.html#subprocess.run>`_
        """
        try:
            run_results = self.run_as_student(**subprocess_run_keyword_args, files_accessible=files_accessible)

        except subprocess.TimeoutExpired as e:
            if test_info is not None:
                test_info.output = self._build_student_output(expected_return_code, expected_output, expected_err,
                                                              None, e.stdout, e.stderr,
                                                              prepend=f'Your Program took longer than {e.timeout} seconds to complete.\n')
            if isinstance(e, these_exceptions_makes_ungradable):
                raise UngradableError(f'{test_info.output}')
            elif test_info is not None:
                self.fail()
        except subprocess.CalledProcessError as e:
            if test_info is not None:
                test_info.output = self._build_student_output(expected_return_code, expected_output, expected_err,
                                                              e.returncode, e.stdout, e.stderr,
                                                              prepend="Your Program Crashed\n")
            if isinstance(e, these_exceptions_makes_ungradable):
                if test_info is not None:
                    raise UngradableError(
                        f'Student Program Crashed on test {test_info.name}. See that test for more info.')
                else:
                    raise UngradableError(f'Student Program Crashed due to the following\n{traceback.format_exc()}')
            elif test_info is not None:
                self.fail()
        except Exception as e:
            if test_info is not None:
                test_info.output = f'Your Program Crashed due to the following\n{traceback.format_exc()}'
            if isinstance(e, these_exceptions_makes_ungradable):
                if test_info is not None:
                    raise UngradableError(
                        f'Student Program Crashed on test {test_info.name}. See that test for more info.')
                else:
                    raise UngradableError(f'Student Program Crashed due to the following\n{traceback.format_exc()}')
            elif test_info is not None:
                self.fail()
        else:
            if test_info is not None:  # check the student answer to see if it is correct
                answer_is_correct = True
                pass_fail_message = []
                if enforce_whitespace:
                    output_cmp = expected_output.__eq__
                else:
                    output_cmp = functools.partial(are_strs_equal_ignoring_whitespace, expected_output)

                if expected_return_code is not None:
                    if run_results.returncode == expected_return_code:
                        pass_fail_message.append("Return Code: Correct")
                    else:
                        pass_fail_message.append("Return Code: Mismatch")
                        answer_is_correct = False
                if expected_output is not None:
                    if output_cmp(run_results.stdout):
                        pass_fail_message.append("Output: Correct")
                    else:
                        pass_fail_message.append("Output: Mismatch")
                        answer_is_correct = False
                if expected_err is not None:
                    if output_cmp(run_results.stderr):
                        pass_fail_message.append("Standard Error: Correct")
                    else:
                        pass_fail_message.append("Standard Error: Mismatch")
                        answer_is_correct = False

                test_info.output = self._build_student_output(expected_return_code, expected_output, expected_err,
                                                              run_results.returncode, run_results.stdout,
                                                              run_results.stderr,
                                                              prepend='\n'.join(pass_fail_message))
                if not answer_is_correct:
                    self.fail()
            return run_results
        finally:
            if test_info:  # add description (how program was run) and message (expected output)
                test_info.message = '\n'.join(
                    [self._build_expected_output(expected_return_code, expected_output, expected_err),
                     self._describe_how_program_was_run(subprocess_run_keyword_args['args'],
                                                        subprocess_run_keyword_args.get('input', None))
                     ])

            # remove any permission granted
            if files_accessible is not None:
                for files in files_accessible.values():
                    subprocess.run(['setfacl', '-x', 'u:sbuser'] + list(files))

    def run_student_program_against_instructor_program(self,
                                                       test_info: UTSGTestCaseInfo,
                                                       instructor_args: list[str],
                                                       student_args: list[str],
                                                       timeout: float,
                                                       instructor_working_directory: Optional[str] = None,
                                                       student_working_directory: Optional[str] = None,
                                                       stdin: Optional[str] = None,
                                                       enforce_whitespace: bool = False,
                                                       check_return_code: bool = True,
                                                       check_output: bool = True,
                                                       check_err: bool = False,
                                                       these_exceptions_makes_ungradable: type | tuple[type, ...] = (),
                                                       files_accessible_to_student: Optional[
                                                           AccessControls] = None) -> None:
        """
        Run the instructor's program and the student's program on the same set of input and then check the student's
        and then check if their outputs are the same. If so the test case passes, otherwise it fails \n
        :param test_info: where to store the results of the test
        :param instructor_args: the command to run the instructor's program along with any command line arguments
        :param student_args: the command to run the student's program along with any command line arguments
        :param timeout: how much time a program has to run before it will be killed
        :param instructor_working_directory: where to run the instructor's program from. Default: /grade/tests
        :param student_working_directory: where to run the student's program from. Default: /grade/student
        :param stdin: what to feed to the program's standard input
        :param enforce_whitespace: whether or not white space should be enforced when checking the output of the programs
        :param check_return_code: whether or not to check the return code of the programs
        :param check_output: whether or not to check the output of the programs
        :param check_err: whether or not to check the stderr of the programs
        :param these_exceptions_makes_ungradable: a tuple of exceptions that if raised should mark the submission as ungradable
        :param files_accessible_to_student: files and directories to the student. By default they only have acess to
          what is in /grade/student
        :return: None
        """
        if instructor_working_directory is None:
            instructor_working_directory = self.tests_dir
        if student_working_directory is None:
            student_working_directory = self.student_dir

        instructor_results = self.run_program(args=instructor_args,
                                              input=stdin,
                                              capture_output=True,
                                              timeout=timeout,
                                              cwd=instructor_working_directory,
                                              text=True)
        # limit student output to be about twice that of the instructor's
        bufsize = len(instructor_results.stdout) * 2 + 500
        self.run_under_test_as_student(test_info=test_info,
                                       files_accessible=files_accessible_to_student,
                                       these_exceptions_makes_ungradable=these_exceptions_makes_ungradable,
                                       expected_output=instructor_results.stdout if check_output else None,
                                       expected_err=instructor_results.stderr if check_err else None,
                                       expected_return_code=instructor_results.returncode if check_return_code else None,
                                       enforce_whitespace=enforce_whitespace, args=student_args, input=stdin,
                                       check=True,
                                       capture_output=True, timeout=timeout, cwd=student_working_directory, text=True,
                                       bufsize=bufsize)

    @staticmethod
    def _describe_how_program_was_run(run_args: list[str], stdin: Optional[str] = None, prepend: str = '',
                                      append: str = '') -> str:
        """
        Helps form the message to be shown to the students on completion of the test \n
        :param run_args: the command used to run the students code
        :param stdin: the standard input provided to the student
        :param prepend: any message to prepend to the output
        :param append: any message to append to the output
        :return: the message string
        """
        program_run_format = 'Your program was run as: {run_command}'
        input_run_format = 'It was provided the following input: {stdin}'

        message = [program_run_format.format(run_command=shlex.join(run_args))]
        if prepend:
            message.insert(0, prepend)
        if stdin is not None:
            message.append(input_run_format.format(stdin=stdin))
        if append:
            message.append(append)
        return '\n'.join(message)

    @staticmethod
    def _build_expected_output(expected_return_code: int | None,
                               expected_output: str | bytes | None,
                               expected_err: str | bytes | None):
        message = []
        if expected_return_code is not None:
            message.append(f'Expected Return Code: {expected_return_code}')
        if expected_output:
            message.append(f'Expected Output: {expected_output}')
        if expected_err:
            message.append(f'Expected Error: {expected_err}')
        return '\n'.join(message)

    @staticmethod
    def _build_student_output(expected_return_code: int | None,
                              expected_output: str | bytes | None,
                              expected_err: str | bytes | None,
                              student_return_code: int | None,
                              student_output: str | bytes | None,
                              student_err: str | bytes | None,
                              prepend: str = '',
                              append: str = ''):

        return_code_message = f"Your Program's Return Code: {student_return_code}"
        output_message = f"Your Program's Output: {student_output}"
        error_message = f"Your Program's Error: {student_err}"
        message = [prepend] if prepend else []

        if student_return_code:  # program didn't exit normally
            # show everything to help debugging
            message.extend([return_code_message, output_message, error_message])
        else:
            if expected_return_code is not None:
                message.append(return_code_message)
            if expected_output:
                message.append(output_message)
            if expected_err:
                message.append(error_message)
        if append:
            message.append(append)
        return '\n\n'.join(message)


class UTSGSubTest(AbstractContextManager):
    """

    """

    @multimethod.multimethod
    def __init__(self, parent_test_case: UTSGTestCase, utsg_test_case_info: UTSGTestCaseInfo, **kwargs):
        """

        :param parent_test_case: The test case this subtest lives inside of.
        :param utsg_test_case_info: The test case info for this subtest
        :param kwargs: Additional arguments to pass to unittest.subTest
        .. note:: Make changes to testCaseUsage.rst that refers to this method upon changes
        """
        self.utsg_test_case_info = utsg_test_case_info
        self.parent_test_case, self.subtest_context_manager = self._common_init(parent_test_case, **kwargs)

    @multimethod.multimethod
    def __init__(self, parent_test_case: UTSGTestCase, name: str, description: str,
                 max_points: float, points_lost_on_failure: float,
                 include_in_results: bool, hidden: bool, **kwargs):
        """

        :param parent_test_case: The test case this subtest lives inside of.
          See UTSGTestCase for the meaning of these parameters
        :param name:
        :param description:
        :param max_points:
        :param points_lost_on_failure:
        :param include_in_results:
        :param hidden:

        :param kwargs: Additional arguments to pass to unittest.subTest
        .. note:: Make changes to testCaseUsage.rst that refers to this method upon changes
        """
        self.utsg_test_case_info = UTSGTestCaseInfo(name, description,
                                                    max_points, points_lost_on_failure,
                                                    include_in_results, hidden)
        self.parent_test_case, self.subtest_context_manager = self._common_init(parent_test_case, **kwargs)

    @staticmethod
    def _common_init(parent_test_case: UTSGTestCase, **kwargs) -> tuple[UTSGTestCase, AbstractContextManager]:
        """
        The parts of init that are common to all versions of it. Generates the values for
        ``parent_test_case``, ``subtest_context_manager``, and ``test_status`` \n
        :param parent_test_case: the parent test that the subtest lives inside
        :param kwargs: Additional arguments to pass to `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_
        :return: a tuple with ``(parent_test_case, subtest_context_manager)``
        """
        return parent_test_case, parent_test_case.subTest(**kwargs)

    def __enter__(self) -> "UTSGSubTest":
        """
        This is the code run when the with statement is entered. Does the same thing as `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_
        but also gives back the subtest so you can modify the values in :py:func:`subtest.utsg_test_case_info <utsg_testcase.UTSGSubTest.__init__>` \n
        :return: The subtest
        """
        super().__enter__()
        self.utsg_test_case_info._status = UTSGTestStatus.RUNNING
        self.subtest_context_manager.__enter__()
        return self

    def __exit__(self, exception_type: Type[BaseException] | None, exception_value: BaseException | None,
                 __traceback: TracebackType | None) -> bool | None:
        """
        Code run when the with statement ends or an exception is triggered within the with statement. Behaves
        identically to the unittest.subTest except that any exceptions aside from AssertionErrors generated within
        the with statement will be reraised. Also sets the test status
        :param exception_type: The type of the exception generated or None if the with statement exited normally
        :param exception_value: The value of the exception generated or None if the with statement exited normally
        :param __traceback: The traceback associated with the exception generated or None
        if the with statement exited normally
        :return:
        """
        super().__exit__(exception_type, exception_value, __traceback)
        suppress_exception = self.subtest_context_manager.__exit__(exception_type, exception_value, __traceback)
        if exception_type is None:
            self.utsg_test_case_info._status = UTSGTestStatus.PASSED
        elif isinstance(exception_value, AssertionError):
            self.utsg_test_case_info._status = UTSGTestStatus.FAILED
        else:
            self.utsg_test_case_info._status = UTSGTestStatus.CRASHED
            suppress_exception = False

        return suppress_exception

if __name__ == '__main__':
    test1 = UTSGTestCase();