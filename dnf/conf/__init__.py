# conf.py
# dnf configuration classes.
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


"""
The configuration classes and routines in yum are splattered over too many
places, hard to change and debug. The new structure here will replace that. Its
goal is to:

* accept configuration options from all three sources (the main config file,
  repo config files, command line switches)
* handle all the logic of storing those and producing related values.
* returning configuration values.
* optionally: asserting no value is overridden once it has been applied
  somewhere (e.g. do not let a new repo be initialized with different global
  cache path than an already existing one).

"""

from __future__ import absolute_import
from __future__ import unicode_literals

from dnf.conf.config import PRIO_DEFAULT, PRIO_MAINCONFIG, PRIO_AUTOMATICCONFIG
from dnf.conf.config import PRIO_REPOCONFIG, PRIO_PLUGINDEFAULT, PRIO_PLUGINCONFIG
from dnf.conf.config import PRIO_COMMANDLINE, PRIO_RUNTIME

from dnf.conf.config import Value
from dnf.conf.config import Option, ListOption, UrlOption, UrlListOption
from dnf.conf.config import PathOption, IntOption, PositiveIntOption
from dnf.conf.config import SecondsOption, BoolOption, FloatOption
from dnf.conf.config import SelectionOption, CaselessSelectionOption
from dnf.conf.config import BytesOption, ThrottleOption

from dnf.conf.config import BaseConfig, MainConf, RepoConf, ModuleConf, ModuleDefaultsConf

from dnf.conf.config import ParsingError, ConfigParser


Conf = MainConf
