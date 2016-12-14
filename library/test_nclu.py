import unittest

import nclu
from ansible.module_utils.basic import *


class FakeModule(object):
    def __init__(self):
        self.reset()

    def exit_json(self, **kwargs):
        self.exit_code = kwargs

    def fail_json(self, **kwargs):
        self.fail_code = kwargs

    def run_command(self, command):
        self.last_command = command
        return self.output

    def mock_output(self, _rc, command, errmsg):
        self.output = (_rc, command, errmsg)

    def reset(self):
        self.exit_code = {}
        self.fail_code = {}
        self.last_command = None
        self.output = (0, "", "")





class TestNclu(unittest.TestCase):
    @classmethod

    def test_command_helper(self):
        module = FakeModule()
        module.mock_output(0, "", "")

        result = command_helper(module, 'add int swp1', 'error out')
        self.assertEqual(module.last_command, "/usr/bin/net add int swp1")
        self.assertEqual(result, "")

    def test_command_helper_error_code(self):
        module = FakeModule()
        module.mock_output(1, "", "")

        result = command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})

    def test_command_helper_error_msg(self):
        module = FakeModule()
        module.mock_output(0, "ERROR: Command not found", "error out")

        result = command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})

    def test_command_helper_no_error_msg(self):
        module = FakeModule()
        module.mock_output(0, "ERROR: Command not found")

        result = command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "ERROR: Command not found"})
