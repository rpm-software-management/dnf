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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


#Constants
#transaction set states
TS_UPDATE = 10
TS_INSTALL = 20
TS_TRUEINSTALL = 30
TS_ERASE = 40
TS_OBSOLETED = 50
TS_OBSOLETING = 60
TS_AVAILABLE = 70


TS_INSTALL_STATES = [TS_INSTALL, TS_TRUEINSTALL, TS_UPDATE, TS_OBSOLETING]
TS_REMOVE_STATES = [TS_ERASE, TS_OBSOLETED]

# Transaction Relationships
TR_UPDATES = 1
TR_UPDATEDBY = 2
TR_OBSOLETES = 3
TR_OBSOLETEDBY = 4
TR_DEPENDS = 5
TR_DEPENDSON = 6

# Transaction Member Sort Colors
# Each node in a topological sort is colored
# White nodes are unseen, black nodes are seen
# grey nodes are in progress
TX_WHITE = 0
TX_GREY = 1
TX_BLACK = 2

# package object file types
PO_FILE = 1
PO_DIR = 2
PO_GHOST = 3
PO_CONFIG = 4
PO_DOC = 5

# package object package types
PO_REMOTEPKG = 1
PO_LOCALPKG = 2
PO_INSTALLEDPKG = 3

# FLAGS
SYMBOLFLAGS = {'>':'GT', '<':'LT', '=': 'EQ', '==': 'EQ', '>=':'GE', '<=':'LE'}
LETTERFLAGS = {'GT':'>', 'LT':'<', 'EQ':'=', 'GE': '>=', 'LE': '<='}

# Constants for plugin config option registration
PLUG_OPT_STRING = 0
PLUG_OPT_INT = 1
PLUG_OPT_FLOAT = 2
PLUG_OPT_BOOL = 3

PLUG_OPT_WHERE_MAIN = 0
PLUG_OPT_WHERE_REPO = 1
PLUG_OPT_WHERE_ALL = 2

# boolean dict:
BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                  '0': False, 'no': False, 'false': False, 'off': False}
