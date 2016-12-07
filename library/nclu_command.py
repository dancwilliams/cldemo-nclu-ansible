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
module: nclu_command
version_added: "2.2"
author: "Cumulus Networks (@CumulusNetworks)"
short_description: Allows running NCLU commands
description:
    - Smart interface to NCLU, allows usage of Command Line utilities
      with proper return values when things are changed or not.
'''

EXAMPLES = '''
nclu_command:
   commands:
     - ip add swp1 10.0.0.1/32
     - ip add swp2 10.0.0.2/32

nclu_command:
   template: |
       {% for iface in interfaces %}
       ip add {{iface}} {{address[iface]}}
       {% endfor %}
   commit: no

nclu_command: commit=yes
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
    (_rc, output, _err) = module.run_command("/usr/bin/net %s"%command)
    if _rc or 'ERROR' in output:
        module.fail_json(msg=errmsg or output)
    return str(output)


def main():
    module = AnsibleModule(argument_spec=dict(
        commands = dict(required=False, type='list'),
        template = dict(required=False, type='str'),
        commit = dict(required=False, type='bool', default=True),
        comment = dict(required=False, type='str', default="")),
        mutually_exclusive=[('commands', 'template')]
    )
    _changed = True
    command_list = module.params.get('commands', None)
    command_string = module.params.get('template', None)
    commit = module.params.get('commit')
    comment = module.params.get('comment')

    commands = []
    if command_list:
        commands = command_list
    elif command_string:
        commands = command_string.splitlines()

    # First, look at the staged commands.
    before = command_helper(module, "pending", "check pending failed")

    # Run all of the the net commands
    output_lines = []
    for line in commands:
        output_lines += [module.run_command("/usr/bin/net %s"%line)]
    output = "\n".join(output_lines)

    # If pending changes changed, report a change.
    after = command_helper(module, "pending", "check pending failed")
    if before == after:
        _changed = False
    else:
        _changed = True

    # Handle a no command situation.
    if not commands and after and commit:
        _changed = True
    if commit and _changed:
        command_helper(module, "commit" if not comment else "commit description '%s'"%comment)

    module.exit_json(changed=_changed, msg=output)

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
