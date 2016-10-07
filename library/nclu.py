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
author: "Cumulus Networks (@CumulusNetworks)"
short_description: Allows running NCLU commands
description:
    - Smart interface to NCLU, allows usage of Command Line utilities
      with proper return values when things are changed or not.
'''

EXAMPLES = '''
nclu: ip add swp1 10.0.0.0/32
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


def main():
    module = AnsibleModule(argument_spec=dict(
        net = dict(required=True, type='str')
    ))
    _changed = True
    command = module.params['net']

    (_rc, pending, _err) = module.run_command("/usr/bin/net pending")
    if _rc or 'ERROR' in pending:
        module.fail_json(msg="check pending failed")

    # run the net command
    (_rc, output, _err) = module.run_command("/usr/bin/net %s"%command)
    if _rc or 'ERROR' in output:
        module.fail_json(msg=output)

    (_rc, pending2, _err) = module.run_command("/usr/bin/net pending")
    if _rc or 'ERROR' in pending2:
        module.fail_json(msg="check pending failed")

    # If pending changes changed, report a change.
    if pending == pending2:
        _changed = False
    else:
        _changed = True

    module.exit_json(changed=_changed, msg=output)

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
