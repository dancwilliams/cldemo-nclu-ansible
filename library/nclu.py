#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, Cumulus Networks <ce-ceng@cumulusnetworks.com>
#
# This file is part of Ansible
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: nclu
version_added: "2.2"
author: "Cumulus Networks"
short_description: Allows running NCLU commands
description:
    - Interface to the Network Command Line Utility, developed to make it easier
      to configure operating systems running ifupdown2 and Quagga, such as
      Cumulus Linux. Command documentation is available at
      https://docs.cumulusnetworks.com/display/DOCS/Network+Command+Line+Utility
options:
    commands:
        description:
            - A list of strings containing the net commands to run.
    template:
        description:
            - A single, multi-line string with jinja2 formatting. This string
              will be broken by lines, and each line will be run through net.
              Mutually exclusive with 'commands'.
    commit:
        description:
            - When present, performs a 'net commit' at the end of the block.
              The option value is a string that will be saved in the commit buffer
              and in the rollback log.
    abort:
        description:
            - Boolean. When true, perform a 'net abort' before the block.
              This cleans out any uncommitted changes in the buffer.
    atomic:
        description:
            - When present, performs a 'net abort' before the block and a
              'net commit' at the end of the block. The option value is a string
              that will be saved in the commit buffer and in the rollback log.
              Mutually exclusive with 'commit' and 'abort'.
'''

EXAMPLES = '''

## Add two interfaces without committing any changes

nclu:
    commands:
        - add int swp1
        - add int swp2

## Add 48 interfaces and commit the change.

nclu:
    template: |
        {% for iface in range(1,49) %}
        add int swp{{i}}
        {% endfor %}
    commit: "Ansible - add swps1-48"

## Atomically add an interface

nclu:
    commands:
        - add int swp1
    atomic: "Ansible - add swp1"
'''

RETURN = '''
changed:
    description: whether the interface was changed
    returned: changed
    type: bool
    sample: True
msg:
    description: human-readable report of success or failure
    returned: always
    type: string
    sample: "interface bond0 config updated"
'''


def command_helper(module, command, errmsg=None):
    """Run a command, catch any nclu errors"""
    (_rc, output, _err) = module.run_command("/usr/bin/net %s"%command)
    if _rc or 'ERROR' in output:
        module.fail_json(msg=errmsg or output)
    return str(output)


def check_pending(module):
    """Check the pending diff of the nclu buffer."""
    pending = command_helper(module, "pending", "Error in pending config. You may want to view `net pending` on this target.")

    delimeter1 = "net add/del commands since the last 'net commit'"
    color1 = '\x1b[94m'
    if delimeter1 in pending:
        pending = pending.split(delimeter1)[0]
        pending = pending.replace('\x1b[94m', '')
    return pending.strip()


def run_nclu(module, command_list, command_string, commit, atomic, abort):
    _changed = False

    commands = []
    if command_list:
        commands = command_list
    elif command_string:
        commands = command_string.splitlines()

    do_commit = False
    do_abort = abort
    description = ""
    if commit or atomic:
        do_commit = True
        if atomic:
            do_abort = True
        description = commit or atomic

    if do_abort:
        command_helper(module, "abort")

    # First, look at the staged commands.
    before = check_pending(module)
    # Run all of the the net commands
    output_lines = []
    for line in commands:
        output_lines += [command_helper(module, line.strip(), "Failed on line %s"%line)]
    output = "\n".join(output_lines)

    # If pending changes changed, report a change.
    after = check_pending(module)
    if before == after:
        _changed = False
    else:
        _changed = True

    # Do the commit.
    if do_commit:
        result = command_helper(module, "commit description '%s'"%description)
        if "commit ignored" in result:
            _changed = False
            command_helper(module, "abort")
        elif command_helper(module, "show commit last") == "":
            _changed = False

    return _changed, output


def main(testing=False):
    module = AnsibleModule(argument_spec=dict(
        commands = dict(required=False, type='list'),
        template = dict(required=False, type='str'),
        abort = dict(required=False, type='bool', default=False),
        commit = dict(required=False, type='str', default=""),
        atomic = dict(required=False, type='str', default="")),
        mutually_exclusive=[('commands', 'template'),
                            ('commit', 'atomic'),
                            ('abort', 'atomic')]
    )
    command_list = module.params.get('commands', None)
    command_string = module.params.get('template', None)
    commit = module.params.get('commit')
    atomic = module.params.get('atomic')
    abort = module.params.get('abort')

    _changed, output = run_nclu(module, command_list, command_string, commit, atomic, abort)
    if not testing:
        module.exit_json(changed=_changed, msg=output)
    elif testing:
        return {"changed": _changed, "msg": output}

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
