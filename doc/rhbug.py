# rhbug.py
# rhbug Sphinx extension.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from docutils import nodes

try:
    import bugzilla
except ImportError:
    bugzilla = None
import json
import os

class Summary(object):
    def __init__(self, cache_fn):
        self.cache_fn = cache_fn

    def __call__(self, bug_id):
        bug_id = int(bug_id)
        summary = self._from_cache(bug_id)
        if summary is not None:
            return summary
        summary = self._from_bugzilla(bug_id)
        self._store_in_cache(bug_id, summary)
        return summary

    def _from_bugzilla(self, bug_id):
        if bugzilla is None:
            return ''
        rhbz = bugzilla.RHBugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi")
        query = rhbz.build_query(bug_id=bug_id)
        bug = rhbz.query(query)[0]
        return bug.summary

    def _from_cache(self, bug_id):
        try:
            with open(self.cache_fn, 'r') as json_file:
                cache = json.load(json_file)
                summary = [entry[1] for entry in cache if entry[0] == bug_id]
                return summary[0]
        except (IOError, IndexError):
            return None

    def _store_in_cache(self, bug_id, summary):
        if bugzilla is None:
            return
        try:
            with open(self.cache_fn, 'r') as json_file:
                cache = json.load(json_file)
        except IOError:
            cache = []
        cache.append((bug_id, summary))
        with open(self.cache_fn, 'w') as json_file:
            json.dump(cache, json_file, indent=4)

def RhBug_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    source = inliner.document.settings._source
    summaries_fn = '%s/summaries_cache' % os.path.dirname(source)
    summary = Summary(summaries_fn)(text)
    link_name = 'Bug %s - %s' % (text, summary)
    url = 'https://bugzilla.redhat.com/show_bug.cgi?id=%s' % text
    node = nodes.reference(rawtext, link_name, refuri=url)
    return [node], []

def setup(app):
    app.add_role('rhbug', RhBug_role)
