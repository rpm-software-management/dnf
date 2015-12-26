# repolist.py
# repolist CLI command.
#
# Copyright (C) 2014  Red Hat, Inc.
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

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.cli import commands
from dnf.i18n import _, ucd, fill_exact_width, exact_width
import dnf.cli.format
import dnf.pycomp
import fnmatch
import logging
import operator
import time

logger = logging.getLogger('dnf')


def _expire_str(repo, md):
    last = time.ctime(md.timestamp) if md else _("unknown")
    if repo.metadata_expire <= -1:
        return _("Never (last: %s)") % last
    elif not repo.metadata_expire:
        return _("Instant (last: %s)") % last
    else:
        num = _num2ui_num(repo.metadata_expire)
        return _("%s second(s) (last: %s)") % (num, last)


def _num2ui_num(num):
    return ucd(dnf.pycomp.format("%d", num, True))


def _repo_match(repo, patterns):
    rid = repo.id.lower()
    rnm = repo.name.lower()
    for pat in patterns:
        if fnmatch.fnmatch(rid, pat):
            return True
        if fnmatch.fnmatch(rnm, pat):
            return True
    return False


def _repo_size(sack, repo):
    ret = 0
    for pkg in sack.query().filter(reponame__eq=repo.id):
        ret += pkg.size
    return dnf.cli.format.format_number(ret)


class RepoListCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    repolist command.
    """

    aliases = ('repolist',)
    summary = _('Display the configured software repositories')
    usage = '[all|enabled|disabled]'

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def run(self, extcmds):
        if len(extcmds) >= 1 and extcmds[0] in ('all', 'disabled', 'enabled'):
            arg = extcmds[0]
            extcmds = extcmds[1:]
        else:
            arg = 'enabled'
        extcmds = [x.lower() for x in extcmds]

        verbose = self.base.conf.verbose

        repos = list(self.base.repos.values())
        repos.sort(key=operator.attrgetter('id'))
        enabled_repos = self.base.repos.enabled()
        term = self.output.term
        on_ehibeg = term.FG_COLOR['green'] + term.MODE['bold']
        on_dhibeg = term.FG_COLOR['red']
        on_hiend = term.MODE['normal']
        tot_num = 0
        cols = []
        for repo in repos:
            if len(extcmds) and not _repo_match(repo, extcmds):
                continue
            (ehibeg, dhibeg, hiend) = '', '', ''
            ui_enabled = ''
            ui_endis_wid = 0
            ui_num = ""
            ui_excludes_num = ''
            force_show = False
            if arg == 'all' or repo.id in extcmds or repo.name in extcmds:
                force_show = True
                (ehibeg, dhibeg, hiend) = (on_ehibeg, on_dhibeg, on_hiend)
            if repo in enabled_repos:
                enabled = True
                if arg == 'enabled':
                    force_show = False
                elif arg == 'disabled' and not force_show:
                    continue
                if force_show or verbose:
                    ui_enabled = ehibeg + _('enabled') + hiend
                    ui_endis_wid = exact_width(_('enabled'))
                    if not verbose:
                        ui_enabled += ": "
                        ui_endis_wid += 2
                if verbose:
                    ui_size = _repo_size(self.base.sack, repo)
                # We don't show status for list disabled
                if arg != 'disabled' or verbose:
                    num = len(self.base.sack.query().filter(
                        reponame__eq=repo.id))
                    ui_num = _num2ui_num(num)
                    tot_num += num
            else:
                enabled = False
                if arg == 'disabled':
                    force_show = False
                elif arg == 'enabled' and not force_show:
                    continue
                ui_enabled = dhibeg + _('disabled') + hiend
                ui_endis_wid = exact_width(_('disabled'))

            if not verbose:
                rid = repo.id
                if enabled and repo.metalink:
                    mdts = repo.metadata.timestamp
                    if mdts > repo.metadata.md_timestamp:
                        rid = '*' + rid
                cols.append((rid, repo.name,
                             (ui_enabled, ui_endis_wid), ui_num))
            else:
                if enabled:
                    md = repo.metadata
                else:
                    md = None
                out = [self.output.fmtKeyValFill(_("Repo-id      : "), repo.id),
                       self.output.fmtKeyValFill(_("Repo-name    : "), repo.name)]

                if force_show or extcmds:
                    out += [self.output.fmtKeyValFill(_("Repo-status  : "),
                                               ui_enabled)]
                if md and md.revision is not None:
                    out += [self.output.fmtKeyValFill(_("Repo-revision: "),
                                               md.revision)]
                if md and md.content_tags:
                    tags = md.content_tags
                    out += [self.output.fmtKeyValFill(_("Repo-tags    : "),
                                               ", ".join(sorted(tags)))]

                if md and md.distro_tags:
                    for (distro, tags) in md.distro_tags.items():
                        out += [self.output.fmtKeyValFill(_("Repo-distro-tags: "),
                                                   "[%s]: %s" % (distro,
                                                   ", ".join(sorted(tags))))]

                if md:
                    out += [
                        self.output.fmtKeyValFill(_("Repo-updated : "),
                                                  time.ctime(md.md_timestamp)),
                        self.output.fmtKeyValFill(_("Repo-pkgs    : "), ui_num),
                        self.output.fmtKeyValFill(_("Repo-size    : "), ui_size)]

                if repo.metalink:
                    out += [self.output.fmtKeyValFill(_("Repo-metalink: "),
                                               repo.metalink)]
                    if enabled:
                        ts = repo.metadata.timestamp
                        out += [self.output.fmtKeyValFill(_("  Updated    : "),
                                                   time.ctime(ts))]
                elif repo.mirrorlist:
                    out += [self.output.fmtKeyValFill(_("Repo-mirrors : "),
                                               repo.mirrorlist)]
                baseurls = repo.baseurl
                if baseurls:
                    out += [self.output.fmtKeyValFill(_("Repo-baseurl : "),
                                               ", ".join(baseurls))]
                elif enabled and md.mirrors:
                    url = "%s (%d more)" % (md.mirrors[0], len(md.mirrors) - 1)
                    out += [self.output.fmtKeyValFill(_("Repo-baseurl : "), url)]

                expire = _expire_str(repo, md)
                out += [self.output.fmtKeyValFill(_("Repo-expire  : "), expire)]

                if repo.exclude:
                    out += [self.output.fmtKeyValFill(_("Repo-exclude : "),
                                               ", ".join(repo.exclude))]

                if repo.include:
                    out += [self.output.fmtKeyValFill(_("Repo-include : "),
                                               ", ".join(repo.include))]

                if ui_excludes_num:
                    out += [self.output.fmtKeyValFill(_("Repo-excluded: "),
                                               ui_excludes_num)]

                if repo.repofile:
                    out += [self.output.fmtKeyValFill(_("Repo-filename: "),
                                               repo.repofile)]

                logger.log(dnf.logging.DEBUG, "%s\n", "\n".join(map(ucd, out)))

        if not verbose and cols:
            #  Work out the first (id) and last (enabled/disalbed/count),
            # then chop the middle (name)...
            id_len = exact_width(_('repo id'))
            nm_len = 0
            st_len = 0
            ui_len = 0

            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if id_len < exact_width(rid):
                    id_len = exact_width(rid)
                if nm_len < exact_width(rname):
                    nm_len = exact_width(rname)
                if st_len < (ui_endis_wid + len(ui_num)):
                    st_len = (ui_endis_wid + len(ui_num))
                # Need this as well as above for: fill_exact_width()
                if ui_len < len(ui_num):
                    ui_len = len(ui_num)
            if arg == 'disabled': # Don't output a status column.
                left = term.columns - (id_len + 1)
            elif exact_width(_('status')) > st_len:
                left = term.columns - (id_len + len(_('status')) + 2)
            else:
                left = term.columns - (id_len + st_len + 2)

            if left < nm_len: # Name gets chopped
                nm_len = left
            else: # Share the extra...
                left -= nm_len
                id_len += left // 2
                nm_len += left - (left // 2)

            txt_rid = fill_exact_width(_('repo id'), id_len)
            txt_rnam = fill_exact_width(_('repo name'), nm_len, nm_len)
            if arg == 'disabled': # Don't output a status column.
                print("%s %s" % (txt_rid, txt_rnam))
            else:
                print("%s %s %s" % (txt_rid, txt_rnam, _('status')))
            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if arg == 'disabled': # Don't output a status column.
                    print("%s %s" % (fill_exact_width(rid, id_len),
                                     fill_exact_width(rname, nm_len, -nm_len)))
                    continue

                if ui_num:
                    ui_num = fill_exact_width(ui_num, ui_len, left=False)
                print("%s %s %s%s" % (fill_exact_width(rid, id_len),
                                      fill_exact_width(rname, nm_len, nm_len),
                                      ui_enabled, ui_num))
        msg = 'Total packages: %s'
        logger.debug(msg, _num2ui_num(tot_num))
