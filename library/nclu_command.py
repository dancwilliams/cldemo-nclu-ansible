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
      Cumulus Linux.
'''

EXAMPLES = '''
nclu:
    commands:
        - ip add swp1 10.0.0.1/32
        - ip add swp2 10.0.0.2/32

nclu:
    template: |
        {% for iface in interfaces %}
        ip add {{iface}} {{address[iface]}}
        {% endfor %}
    commit: true

nclu:
    commit: true
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
    pending = command_helper(module, "pending", "check pending failed")

    delimeter1 = "net add/del commands since the last 'net commit'"
    color1 = '\x1b[94m'
    if delimeter1 in pending:
        pending = pending.split(delimeter1)[0]
        pending = pending.replace('\x1b[94m', '')
    return pending.strip()


def main():
    module = AnsibleModule(argument_spec=dict(
        commands = dict(required=False, type='list'),
        template = dict(required=False, type='str'),
        commit = dict(required=False, type='str', default=""),
        atomic = dict(required=False, type='str', default="")),
        mutually_exclusive=[('commands', 'template'),
                            ('commit', 'atomic')]
    )
    _changed = True
    command_list = module.params.get('commands', None)
    command_string = module.params.get('template', None)
    commit = module.params.get('commit')
    atomic = module.params.get('atomic')

    commands = []
    if command_list:
        commands = command_list
    elif command_string:
        commands = command_string.splitlines()

    do_commit = False
    do_abort = False
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
        output_lines += [command_helper(module, line)]
    output = "\n".join(output_lines)

    # If pending changes changed, report a change.
    after = check_pending(module)
    if before == after:
        _changed = False
    else:
        _changed = True

    # Do the commit.
    if do_commit:
        command_helper(module, "commit description '%s'"%description)
        if command_helper(module, "show commit last") == "":
            _changed = False

    module.exit_json(changed=_changed, msg=output)

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
