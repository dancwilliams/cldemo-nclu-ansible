
import unittest

import nclu
import sys
import time
import StringIO
from ansible.module_utils.basic import *



class FakeModule(object):
    """Fake NCLU module to check the logic of the ansible module.

    We have two sets of tests: fake and real. Real tests only run if
    NCLU is installed on the testing machine (it should be a Cumulus VX
    VM or something like that).

    Fake tests are used to test the logic of the ansible module proper - that
    the right things are done when certain feedback is received.

    Real tests are used to test regressions against versions of NCLU. This
    FakeModule mimics the output that is used for screenscraping. If the real
    output differs, the real tests will catch that.

    To prepare a VX:
      sudo apt-get update
      sudo apt-get install python-setuptools git gcc python-dev libssl-dev
      sudo easy_install pip
      sudo pip install ansible nose coverage
      # git the module and cd to the directory
      nosetests --with-coverage --cover-package=nclu --cover-erase --cover-branches

    If a real test fails, it means that there is a risk of a version split, and
    that changing the module will break for old versions of NCLU if not careful.
    """

    def __init__(self, **kwargs):
        self.reset()

    def exit_json(self, **kwargs):
        self.exit_code = kwargs

    def fail_json(self, **kwargs):
        self.fail_code = kwargs

    def run_command(self, command):
        """Run an NCLU command"""

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
        """Prepare a command to mock certain output"""

        self.mocks[command] = (_rc, output, _err)

    def reset(self):
        self.params = {}
        self.exit_code = {}
        self.fail_code = {}
        self.command_history = []
        self.mocks = {}
        self.pending = ""
        self.last_commit = ""


def skipUnlessNcluInstalled(original_function):
    if os.path.isfile('/usr/bin/net'):
        return original_function
    else:
        return unittest.skip('only run if nclu is installed')


class TestNclu(unittest.TestCase):

    def test_command_helper(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net add int swp1", 0, "", "")

        result = nclu.command_helper(module, 'add int swp1', 'error out')
        self.assertEqual(module.command_history[-1], "/usr/bin/net add int swp1")
        self.assertEqual(result, "")

    def test_command_helper_error_code(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 1, "", "")

        result = nclu.command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})

    def test_command_helper_error_msg(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 0,
                           "ERROR: Command not found", "")

        result = nclu.command_helper(module, 'fake fail command', 'error out')
        self.assertEqual(module.fail_code, {'msg': "error out"})

    def test_command_helper_no_error_msg(self):
        module = FakeModule()
        module.mock_output("/usr/bin/net fake fail command", 0,
                           "ERROR: Command not found", "")

        result = nclu.command_helper(module, 'fake fail command')
        self.assertEqual(module.fail_code, {'msg': "ERROR: Command not found"})

    def test_empty_run(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module, None, None, False, False, False, "")
        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net pending'])
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, False)

    def test_command_list(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module, ['add int swp1', 'add int swp2'],
                                        None, False, False, False, "")

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending'])
        self.assertNotEqual(len(module.pending), 0)
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, True)

    def test_command_list_commit(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module,
                                        ['add int swp1', 'add int swp2'],
                                        None, True, False, False, "committed")

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'committed'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, True)


    def test_command_atomic(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module,
                                        ['add int swp1', 'add int swp2'],
                                        None, False, True, False, "atomically")

        self.assertEqual(module.command_history, ['/usr/bin/net abort',
                                                  '/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'atomically'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, True)

    def test_command_abort_first(self):
        module = FakeModule()
        module.pending = "dirty"
        nclu.run_nclu(module, None, None, False, False, True, "")

        self.assertEqual(len(module.pending), 0)

    def test_command_template_commit(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module, None,
                                        "    add int swp1\n    add int swp2",
                                        True, False, False, "committed")

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net add int swp1',
                                                  '/usr/bin/net add int swp2',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'committed'",
                                                  '/usr/bin/net show commit last'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, True)

    def test_commit_ignored(self):
        module = FakeModule()
        changed, output = nclu.run_nclu(module, None, None, True, False, False, "ignore me")

        self.assertEqual(module.command_history, ['/usr/bin/net pending',
                                                  '/usr/bin/net pending',
                                                  "/usr/bin/net commit description 'ignore me'",
                                                  '/usr/bin/net abort'])
        self.assertEqual(len(module.pending), 0)
        self.assertEqual(module.fail_code, {})
        self.assertEqual(changed, False)


    def test_command_list_branches(self):
        input1 = ["a", "b"]
        input2 = "a\nb"

        self.assertEqual(nclu.get_command_list(input1, None), input1)
        self.assertEqual(nclu.get_command_list(None, input2), input1)
        self.assertEqual(nclu.get_command_list(input1, input2), input1)
        self.assertEqual(nclu.get_command_list(None, None), [])


    def test_commit_behavior_branches(self):
        #commit, atomic, abort
        self.assertEqual(nclu.get_commit_behavior(True, True, True),    (True, True))
        self.assertEqual(nclu.get_commit_behavior(True, True, False),   (True, True))
        self.assertEqual(nclu.get_commit_behavior(True, False, True),   (True, True))
        self.assertEqual(nclu.get_commit_behavior(True, False, False),  (True, False))
        self.assertEqual(nclu.get_commit_behavior(False, True, True),   (True, True))
        self.assertEqual(nclu.get_commit_behavior(False, True, False),  (True, True))
        self.assertEqual(nclu.get_commit_behavior(False, False, True),  (False, True))
        self.assertEqual(nclu.get_commit_behavior(False, False, False), (False, False))

    @skipUnlessNcluInstalled
    def test_vx_command_helper(self):

        # gymnastics for ansible
        stdin = sys.stdin
        argv = sys.argv
        sys.argv = []
        sys.stdin = StringIO.StringIO('{"ANSIBLE_MODULE_ARGS": {}}')

        # test
        module = AnsibleModule(argument_spec=dict())
        nclu.command_helper(module, 'abort')
        nclu.command_helper(module, 'del interface swp1')
        nclu.command_helper(module, 'commit')
        nclu.command_helper(module, 'abort')


        # gymnastics to fix ansible
        sys.stdin = stdin
        sys.argv = argv


    @skipUnlessNcluInstalled
    def test_vx_show_pending(self):

        # gymnastics for ansible
        stdin = sys.stdin
        argv = sys.argv
        sys.argv = []
        sys.stdin = StringIO.StringIO('{"ANSIBLE_MODULE_ARGS": {}}')

        # start by doing some cleanup
        module = AnsibleModule(argument_spec=dict())
        nclu.command_helper(module, 'abort')
        nclu.command_helper(module, 'del interface swp1')
        nclu.command_helper(module, 'commit')
        nclu.command_helper(module, 'abort')

        #
        nclu.command_helper(module, 'add interface swp1')
        pending = nclu.check_pending(module)
        self.assertTrue('swp1' in pending)
        nclu.command_helper(module, 'abort')
        pending = nclu.check_pending(module)
        self.assertTrue('swp1' not in pending)

        # gymnastics to fix ansible
        sys.stdin = stdin
        sys.argv = argv

    @skipUnlessNcluInstalled
    def test_vx_run_list_twice(self):

        # gymnastics for ansible
        stdin = sys.stdin
        argv = sys.argv
        sys.argv = []
        sys.stdin = StringIO.StringIO('{"ANSIBLE_MODULE_ARGS": {}}')

        # start by doing some cleanup
        module = AnsibleModule(argument_spec=dict())
        nclu.command_helper(module, 'abort')
        nclu.command_helper(module, 'del interface swp1')
        nclu.command_helper(module, 'commit')
        nclu.command_helper(module, 'abort')

        # run the test
        changed, output = nclu.run_nclu(module, ['add int swp1'],
                                        None, False, True, False, "atomically")
        self.assertEqual(changed, True)
        changed, output = nclu.run_nclu(module, ['add int swp1'],
                                        None, False, True, False, "atomically")
        self.assertEqual(changed, False)

        # gymnastics to fix ansible
        sys.stdin = stdin
        sys.argv = argv

    @skipUnlessNcluInstalled
    def test_main(self):

        # gymnastics for ansible
        stdin = sys.stdin
        argv = sys.argv
        sys.argv = []
        sys.stdin = StringIO.StringIO('{"ANSIBLE_MODULE_ARGS": {}}')
        nclu.main(testing=True)

        # gymnastics to fix ansible
        sys.stdin = stdin
        sys.argv = argv
