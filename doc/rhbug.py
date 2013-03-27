# rhbug.py
# rhbug Sphinx extension.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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

def RhBug_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    link_name = 'Bug %s' % text
    url = 'https://bugzilla.redhat.com/show_bug.cgi?id=%s' % text
    node = nodes.reference(rawtext, link_name, refuri=url)
    return [node], []

def setup(app):
    app.add_role('rhbug', RhBug_role)
