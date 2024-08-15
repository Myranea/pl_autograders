import unittest_style_grader
from typing import TypedDict


class ParamDict(TypedDict):
    desc: str
    returnCode: int

class TestSuite(unittest_style_grader.UTSGTestCase):
    extraInfo: ParamDict

    @classmethod
    def setUpClass(cls) -> None:
        super.setUpClass()
        
    def myTest(self):
        self.extra_info['desc'] = 'Hi'


if __name__ == '__main__':
    unittest_style_grader.run_tests()