import json
import pathlib
import traceback
import unittest
import unittest_style_grader
import tempfile
import os


def run_tests():
    
    with tempfile.TemporaryDirectory() as gradingLocation:
        grade_dir = pathlib.Path('/grade' if 'GRADE_DIR' not in os.environ else os.environ['GRADE_DIR'])
        plDirs = os.listdir(grade_dir)
        for f in plDirs:
            src_path = os.path.join(grade_dir, f)
            dst_path = os.path.join(pathlib.Path(gradingLocation), f)
            os.rename(src_path, dst_path)
        unittest_style_grader.UTSGTestCase.grade_dir_setter(pathlib.Path(gradingLocation))
        if not unittest_style_grader.UTSGTestCase.results_dir.is_dir():
            unittest_style_grader.UTSGTestCase.results_dir.mkdir(parents=True)
        result_location = unittest_style_grader.UTSGTestCase.results_dir / 'results.json'
        tests_directory = unittest_style_grader.UTSGTestCase.tests_dir
        test_results = unittest_style_grader.UTSGTestResult()
        
    
        try:
            tests = unittest.defaultTestLoader.discover(str(tests_directory))
            # currently a bug in python https://bugs.python.org/issue18848 causes unittest.TestResult.startTestRun
            # and unittest.TestResult.stopTestRun to not be called if an implementation of unittest.TestResult is provided
            # so I have to call them manually. The bug is still present in python 3.10 despite being reported back in 2013
            # if it ever gets fixed, we can remove these lines
            test_results.startTestRun()
            tests.run(test_results)
            test_results.stopTestRun()
        except unittest_style_grader.UngradableError as ungradeable_reason:
            print("ungradable")
            with open(result_location, 'w') as result_file:
                test_results.output = ungradeable_reason.message
                test_results.gradable = False
                test_results.score = 0.0
                json.dump(test_results.utsg_results, result_file)
        except Exception:
            print('Other Exception')
            with open(result_location, 'w') as result_file:
                test_results.output = traceback.format_exc()
                test_results.gradable = False
                test_results.score = 0.0
                json.dump(test_results.utsg_results, result_file)
        finally:
            for error in test_results.errors:
                print(error[0], error[1])
            with open(str(result_location)) as result_file:
                print(result_file.read())
        os.mkdir(grade_dir.name + '/results')
        results_dir = os.listdir(gradingLocation + '/results')
        for f in results_dir:
            src_path = os.path.join(gradingLocation + '/results', f)
            dst_path = os.path.join(grade_dir.name + '/results', f)
            os.rename(src_path, dst_path)