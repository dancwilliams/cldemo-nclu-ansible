# This test script can be used to test the NCLU module with a fake NCLU shim.
# On a Cumulus box, you can use test_nclu_vx for proper systems integration
# testing

import unittest

import nclu
from ansible.module_utils.basic import *



class FakeModule(object):
    def __init__(self, **kwargs):
        self.reset()

    def exit_json(self, **kwargs):
        self.exit_code = kwargs

    def fail_json(self, **kwargs):
        self.fail_code = kwargs

    def run_command(self, command):
        self.command_history.append(command)
        if command == "/usr/bin/net pending":
            return (0, self.pending, "")
        elif command == "/usr/bin/net abort":
            self.pending = ""
            return (0, "", "")
        elif command.startswith("/usr/bin/net commit"):
            if self.pending:
                self.last_commit = self.pending
                self.pending = ""
                return (0, "", "")
            else:
                return (0, "commit ignored...there were no pending changes", "")
        elif command == "/usr/bin/net show commit last":
            return (0, self.last_commit, "")
        else:
            self.pending += command
            return self.mocks.get(command, (0, "", ""))

    def mock_output(self, command, _rc, output, _err):
        self.mocks[command] = (_rc, output, _err)

    def reset(self):
        self.params = {}
        self.exit_code = {}
        self.fail_code = {}
        self.command_history = []
        self.mocks = {}
        self.pending = ""
        self.last_commit = ""


def skipUnlessCumulus(original_function):
    try:
        my_os = file('/etc/lsb-release').read()
        if 'cumulus' not in my_os.lower():
            return unittest.skip('only run on cumulus')
    except:
        return unittest.skip('only run on cumulus')
    return original_function


class TestNclu(unittest.TestCase):

    def test_command_helper(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net add int swp1", 0, "", "")

        result = nclu.command_helper(module, 'add int swp1', 'error out')
        self.assertEqual(module.command_history[-1], "/usr/bin/net add int swp1")
        self.assertEqual(module.exit_code, {})
        self.assertEqual(result, "")

    def test_command_helper_error_code(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 1, "", "")

        result = nclu.command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})
        self.assertEqual(module.exit_code, {})

    def test_command_helper_error_msg(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 0, "ERROR: Command not found", "")

        result = nclu.command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})
        self.assertEqual(module.exit_code, {})

    def test_command_helper_no_error_msg(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 0, "ERROR: Command not found", "")

        result = nclu.command_helper(module, 'fake fail command')
        self.assertEqual(module.fail_code, {'msg': "ERROR: Command not found"})
        self.assertEqual(module.exit_code, {})

    def test_empty_run(self):
        module = FakeModule()
        nclu.run_nclu(module, None, None, False, "", "")
        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net pending'])
        self.assertEqual(module.exit_code['changed'], False)

    def test_command_list(self):
        module = FakeModule()
        nclu.run_nclu(module, ['add int swp1', 'add int swp2'], None, "", "", False)

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending'])
        self.assertNotEqual(len(module.pending), 0)
        self.assertEqual(module.exit_code['changed'], True)

    def test_command_list_commit(self):
        module = FakeModule()
        nclu.run_nclu(module, ['add int swp1', 'add int swp2'], None, "committed", "", False)

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'committed'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.exit_code['changed'], True)


    def test_command_atomic(self):
        module = FakeModule()
        nclu.run_nclu(module, ['add int swp1', 'add int swp2'], None, "", "atomically", False)

        self.assertEqual(module.command_history, ['/usr/bin/net abort',
                                                  '/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'atomically'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.exit_code['changed'], True)

    def test_command_abort_first(self):
        module = FakeModule()
        module.pending = "dirty"
        nclu.run_nclu(module, None, None, "", "", True)

        self.assertEqual(len(module.pending), 0)

    def test_command_template_commit(self):
        module = FakeModule()
        nclu.run_nclu(module, None, "    add int swp1\n    add int swp2", "committed", "", False)

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'committed'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.exit_code['changed'], True)

    def test_commit_ignored(self):
        module = FakeModule()
        nclu.run_nclu(module, None, None, "ignore me", "", False)

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'ignore me'",
                                                  '/usr/bin/net abort'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.exit_code['changed'], False)


    @skipUnlessCumulus
    def test_vx_command_helper(self):
        module = AnsibleModule(argument_spec=dict())
