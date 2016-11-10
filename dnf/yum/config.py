# Copyright (C) 2016  Red Hat, Inc.
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

from dnf.conf.config import BoolOption
from dnf.conf.config import ListOption
from dnf.conf.config import MainConf
from dnf.conf.config import PathOption
from dnf.conf.config import PositiveIntOption
from dnf.conf.config import SecondsOption
from dnf.conf.config import inherit


class YumConf(MainConf):
    def __init__(self):
        super(YumConf, self).__init__()

        self._add_inherited_option(super(YumConf, self), [
            'alwaysprompt', 'assumeno', 'assumeyes', 'bandwidth',
            'bugtracker_url', 'cachedir', 'color',
            'color_list_available_downgrade',
            'color_list_available_install', 'color_list_available_reinstall',
            'color_list_available_upgrade', 'color_list_installed_extra',
            'color_list_installed_newer', 'color_list_installed_older',
            'color_list_installed_reinstall', 'color_search_match',
            'color_update_installed', 'color_update_local', 'color_update_remote',
            'config_file_path',
            'debug_solver', 'debuglevel', 'defaultyes', 'deltarpm',
            'deltarpm_percentage', 'disable_excludes', 'diskspacecheck',
            'downloadonly', 'enabled', 'enablegroups', 'errorlevel',
            'excludepkgs', 'exit_on_lock', 'fastestmirror', 'gpgcheck',
            'group_package_types', 'history_list_view', 'history_record',
            'history_record_packages', 'includepkgs', 'install_weak_deps',
            'installonlypkgs', 'installroot', 'ip_resolve', 'localpkg_gpgcheck',
            'logdir', 'max_parallel_downloads', 'metadata_timer_sync', 'minrate',
            'multilib_policy', 'obsoletes', 'password', 'plugins', 'pluginpath',
            'pluginconfpath', 'protected_packages',
            'proxy', 'proxy_password', 'proxy_username', 'recent',
            'repo_gpgcheck', 'reposdir', 'reset_nice', 'retries', 'rpmverbosity',
            'showdupesfromrepos', 'sslcacert', 'sslclientcert', 'sslclientkey',
            'sslverify', 'strict', 'throttle', 'tsflags',
            'upgrade_group_objects_upgrade', 'username'])

        self._add_option('exclude', self._get_option('excludepkgs'))
        self._add_option('persistdir', PathOption("/var/lib/yum"))
        self._add_option('system_cachedir', PathOption("/var/lib/yum"))
        self._add_option('keepcache', BoolOption(True))
        self._add_option('installonly_limit',
                         PositiveIntOption(3, range_min=2,
                                           names_of_0=["0", "<off>"]))
        self._add_option('timeout', SecondsOption(30))
        self._add_option('metadata_expire', SecondsOption(60 * 60 * 6))  # 6 hours
        self._add_option('best', BoolOption(True))
        self._add_option('skip_broken', not self._get_option("best"))
        self._add_option('clean_requirements_on_remove', BoolOption(False))

    def _add_inherited_option(self, parent, options):
        for option_name in options:
            self._add_option(option_name,
                             inherit(parent._get_option(option_name)))
