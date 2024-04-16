**To Make Test Cases**
==========================

.. note:: TODO document UngradableError and add appropriate references

.. _utsgTestCaseInfo:

UTSGTestCaseInfo
================
A data class

.. autoclass:: utsg_testcase.UTSGTestCaseInfo

Methods 
-------

.. autofunction:: utsg_testcase.UTSGTestCaseInfo.as_prairielearn_json_dict

.. _utsgTestCase:

UTSGTestCase
============

.. note:: TODO: Add description for the class UTSGTestCase

Instance Methods
----------------

.. autofunction:: utsg_testcase.UTSGTestCase.__init__

.. note:: TODO: Add description for setUpClass classmethod

.. autofunction:: utsg_testcase.UTSGTestCase.add_graded_subTest

.. autofunction:: utsg_testcase.UTSGTestCase.run_program

.. autofunction:: utsg_testcase.UTSGTestCase.run_as_student

.. autofunction:: utsg_testcase.UTSGTestCase.run_under_test_as_student

.. autofunction:: utsg_testcase.UTSGTestCase.run_student_program_against_instructor_program

Static Methods
--------------

.. autofunction:: utsg_testcase.UTSGTestCase._describe_how_program_was_run

.. note:: TODO: Add descriptions for _build_student_output and _build_expected_output

.. autofunction:: utsg_testcase.UTSGTestCase._build_student_output

.. _utsgSubTest:

UTSGSubTest
===========

.. note:: TODO: Add description for the class UTSGSubTest

Instance Methods
----------------

.. py:function:: utsg_testcase.UTSGSubTest.__init__(self, parent_test_case: UTSGTestCase, utsg_test_case_info: UTSGTestCaseInfo, **kwargs)
    
    :param parent_test_case: The test case this subtest lives inside of.
    :param utsg_test_case_info: The test case info for this subtest
    :param kwargs: Additional arguments to pass to `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_
    
    .. note:: TODO add a doctest for this entry

.. py:function:: utsg_testcase.UTSGSubTest.__init__(self, parent_test_case: UTSGTestCase, name: str, description: str, max_points: float, points_lost_on_failure: float, include_in_results: bool, hidden: bool, **kwargs)
    :noindex:

    :param parent_test_case: The test case this subtest lives inside of.
          See :ref:`UTSGTestCase <utsgTestCase>` for the meaning of these parameters
    :param name:
    :param description:
    :param max_points:
    :param points_lost_on_failure:
    :param include_in_results:
    :param hidden:
    :param kwargs: Additional arguments to pass to `unittest.subTest <https://docs.python.org/3/library/unittest.html#unittest.TestCase.subTest>`_

    .. note:: TODO add a doctest for this entry

.. autofunction:: utsg_testcase.UTSGSubTest.__enter__

Static Methods
--------------

.. autofunction:: utsg_testcase.UTSGSubTest._common_init