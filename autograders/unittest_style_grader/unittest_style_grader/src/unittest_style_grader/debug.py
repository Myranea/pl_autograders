from unittest_style_grader import UTSGTestCase
import pathlib

print(UTSGTestCase.grade_dir)

UTSGTestCase.grade_dir_setter(pathlib.Path('/home/myranea'))

print(UTSGTestCase.grade_dir)
print(UTSGTestCase.student_dir)
print(UTSGTestCase.data_dir)
print(UTSGTestCase.results_dir)
print(UTSGTestCase.tests_dir)