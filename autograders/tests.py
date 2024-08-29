import unittest_style_grader
from typing import TypedDict

print("I was imported")

class ParamDict(TypedDict):
    desc: str
    returnCode: int

class TestSuite(unittest_style_grader.UTSGTestCase[ParamDict]):
    extra_info: ParamDict

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        
    def test_example(self):
        self.extra_info['desc'] = 'Hi'


if __name__ == '__main__':
    unittest_style_grader.run_tests()