# Copyright 2004, 2009 Toby Dickenson
# Copyright 2014-2015 Aaron Gallagher
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject
# to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import collections
import json
import os
import modulefinder
import sys
import tempfile

from twisted.python import dist3, reflect


class mymf(modulefinder.ModuleFinder):
    def __init__(self, *args, **kwargs):
        self._depgraph = collections.defaultdict(set)
        self._types = {}
        self._last_caller = None
        modulefinder.ModuleFinder.__init__(self, *args, **kwargs)

    def import_hook(self, name, caller=None, fromlist=None, level=None):
        old_last_caller = self._last_caller
        try:
            self._last_caller = caller
            return modulefinder.ModuleFinder.import_hook(
                self, name, caller, fromlist)
        finally:
            self._last_caller = old_last_caller

    def import_module(self, partnam, fqname, parent):
        r = modulefinder.ModuleFinder.import_module(
            self, partnam, fqname, parent)
        if (
                r is not None
                and self._last_caller is not None
                and self._last_caller.__name__ != '__main__'
                and 'twisted' in r.__name__):
            self._depgraph[self._last_caller.__name__].add(r.__name__)
        return r

    def load_module(self, fqname, fp, pathname, (suffix, mode, type)):
        r = modulefinder.ModuleFinder.load_module(
            self, fqname, fp, pathname, (suffix, mode, type))
        if r is not None:
            self._types[r.__name__] = type
        return r

    def as_json(self):
        return {
            'depgraph': {
                name: dict.fromkeys(deps, 1)
                for name, deps in self._depgraph.iteritems()},
            'types': self._types,
        }


def main(target):
    mf = mymf(sys.path[:], 0, [])

    moduleNames = []
    for path, dirnames, filenames in os.walk(target):
        if 'test' in dirnames:
            dirnames.remove('test')
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            if filename == '__init__.py':
                continue
            if '-' in filename:
                # a script like update-documentation.py
                continue
            moduleNames.append(
                reflect.filenameToModuleName(os.path.join(path, filename)))

    with tempfile.NamedTemporaryFile() as tmpfile:
        for moduleName in moduleNames:
            tmpfile.write('import %s\n' % moduleName)
        tmpfile.flush()
        mf.run_script(tmpfile.name)

    with open('twisted-deps.json', 'wb') as outfile:
        json.dump(mf.as_json(), outfile)

    port_status = {}
    for module in dist3.modules:
        port_status[module] = 'ported'
    for module in dist3.almostModules:
        port_status[module] = 'almost-ported'

    with open('twisted-ported.json', 'wb') as outfile:
        json.dump(port_status, outfile)


if __name__ == '__main__':
    main(*sys.argv[1:])
