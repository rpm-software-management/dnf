# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Yum constants. Usually dealing with rpm magic numbers.
"""

#transaction set states
TS_UPDATE = 10
TS_INSTALL = 20
TS_ERASE = 40
TS_OBSOLETED = 50
TS_OBSOLETING = 60
TS_AVAILABLE = 70
TS_UPDATED = 90
TS_FAILED = 100

TS_INSTALL_STATES = [TS_INSTALL, TS_UPDATE, TS_OBSOLETING]
TS_REMOVE_STATES = [TS_ERASE, TS_OBSOLETED, TS_UPDATED]

# Transaction Relationships
TR_UPDATES = 1
TR_UPDATEDBY = 2
TR_OBSOLETES = 3
TR_OBSOLETEDBY = 4
TR_DEPENDS = 5
TR_DEPENDSON = 6

#  Cut over for when we should just give up and load everything.
#  The main problem here is not so much SQLite dying (although that happens
# at large values: http://sqlite.org/limits.html#max_variable_number) but that
# but SQLite going really slow when it gets medium sized values (much slower
# than just loading everything and filtering it in python).
PATTERNS_MAX = 8
#  We have another value here because name is indexed and sqlite is _much_
# faster even at large numbers of patterns.
PATTERNS_INDEXED_MAX = 128
