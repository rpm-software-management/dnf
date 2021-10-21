..
  Copyright (C) 2014-2016 Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, write to the
  Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
  02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
  source code or documentation are not subject to the GNU General Public
  License and may only be used or replicated with the express permission of
  Red Hat, Inc.

###################
 DNF Release Notes
###################

====================
4.10.0 Release Notes
====================

- New features:
  - Add support for autodetecting packages to be excluded from being installed as weak dependencies (RhBug:1699672)
  - Add support for excluding packages to be installed as weak dependencies (RhBug:1699672)
  - Add fail_fast parameter to download_payloads methods for use in reposync

- Bug fixes:
  - Acquire all relevant locks during "dnf clean"
  - API: Raise CompsError when group/env not found in install_group and install_environment (RhBug:1947958)

Bugs fixed in 4.10.0:

* :rhbug:`1699672`
* :rhbug:`1947958`

===================
4.9.0 Release Notes
===================

- New features:
  - [API] Add method "set_or_append_opt_value" to BaseConfig (RhBug:1967925)
  - Add aliases for commands: info, updateinfo, provides (RhBug:1938333)
  - Add report about demodularized rpms into module info (RhBug:1805260)

- Bug fixes:
  - Remove DNSSEC errors on COPR group email keys
  - Documentation inprovements - bugs: 1938352, 1993899, 1963704

Bugs fixed in 4.9.0:

* :rhbug:`1993899`
* :rhbug:`1805260`
* :rhbug:`1938352`
* :rhbug:`1967925`
* :rhbug:`1963704`
* :rhbug:`1938333`

===================
4.8.0 Release Notes
===================

- Do not assume that a remote rpm is complete if present
- Use positive percentage for "Failed delta RPMs" message
- Remove redundant new line in Groups output
- Format empty group names outputs to <name-unset>
- [doc] Document default colors
- Use rpmkeys alone to verify signature

- Bug fixes:
  - Bugs fixed (RhBug:1946975,1955309)
  - Add dnf.error message to explain rpm.error traceback when package not found after resolving a transaction (RhBug:1815327,1887293,1909845)

Bugs fixed in 4.8.0:

* :rhbug:`1955309`
* :rhbug:`1950229`
* :rhbug:`1887293`
* :rhbug:`1946975`

===================
4.7.0 Release Notes
===================

- Improve repo config path ordering to fix a comps merging issue (RhBug:1928181)
- Keep reason when package is removed (RhBug:1921063)
- Improve mechanism for application of security filters (RhBug:1918475)
- [doc] Add description for new API
- [API] Add new method for reset of security filters
- [doc] Improve documentation for Hotfix repositories
- [doc] fix: "makecache" command downloads only enabled repositories
- Use libdnf.utils.checksum_{check,value}
- [doc] Add info that maximum parallel downloads is 20
- Increase loglevel in case of invalid config options
- [doc] installonly_limit documentation follows behavior
- Prevent traceback (catch ValueError) if pkg is from cmdline
- Add documentation for config option sslverifystatus (RhBug:1814383)

- Security fixes:
  - Check for specific key string when verifing signatures (RhBug:1915990)
  - Use rpmkeys binary to verify package signature (RhBug:1915990)

- Bug fixes:
  - Bugs fixed (RhBug:1916783)
  - Preserve file mode during log rotation (RhBug:1910084)

Bugs fixed in 4.7.0:

* :rhbug:`1910084`
* :rhbug:`1921063`
* :rhbug:`1918475`
* :rhbug:`1814383`
* :rhbug:`1928181`

===================
4.6.1 Release Notes
===================

- Fix recreate script
- Add unit test for fill_sack_from_repos_in_cache (RhBug:1865803)
- Add docs and examples for fill_sack_from_repos_in_cache (RhBug:1865803)
- [spec] remove python2 support
- Remove problematic language
- The noroot plugin no longer exists, remove mention
- Run tests for fill_sack_from_repos_in_cache in installroot (RhBug:1865803)
- expand history to full term size when output is redirected (RhBug:1852577) (RhBug:1852577,1906970)
- [doc] Fix: "sslcacert" contains path to the file
- [doc] Added proxy ssl configuration options, increase libdnf require
- Set persistdir and substitutions for fill_sack_from_repos_in_cache tests (RhBug:1865803)
- Update documentation for module_obsoletes and module_stream_switch
- print additional information when verifying GPG key using DNS

- Bug fixes:
  - Bugs fixed (RhBug:1897573)
  - Remove hardcoded logfile permissions (RhBug:1910084)
  - Enhanced detection of plugins removed in transaction (RhBug:1929163)

Bugs fixed in 4.6.1:

* :rhbug:`1852577`
* :rhbug:`1910084`
* :rhbug:`1897573`
* :rhbug:`1929163`
* :rhbug:`1865803`
* :rhbug:`1906970`

===================
4.6.0 Release Notes
===================

- Log scriptlets output also for API users (RhBug:1847340)
- Fix module remove --all when no match spec (RhBug:1904490)
- yum.misc.decompress() to handle uncompressed files (RhBug:1895059)
- Make an error message more informative (RhBug:1814831)
- Add deprecation notice to help messages of deplist
- Remove Base._history_undo_operations() as it was replaced with transaction_sr code
- cli/output: Return number of listed packages from listPkgs()
- Clean up history command error handling
- [doc] Describe install with just a name and obsoletes (RhBug:1902279)
- Add api function fill_sack_from_repos_in_cache to allow loading a repo cache with repomd and (solv file or primary xml) only (RhBug:1865803)
- Packages installed/removed via DNF API are logged into dnf.log (RhBug:1855158)
- Support comps groups in history redo (RhBug:1657123,1809565,1809639)
- Support comps groups in history rollback (RhBug:1657123,1809565,1809639)
- Support comps groups in history undo (RhBug:1657123,1809565,1809639)
- New optional parameter for filter_modules enables following modular obsoletes based on a config option module_obsoletes
- Add get_header() method to the Package class (RhBug:1876606)
- Fix documentation of globs not supporting curly brackets (RhBug:1913418)

- New features:
  - Add api function fill_sack_from_repos_in_cache to allow loading a repo cache with repomd and (solv file or primary xml) only (RhBug:1865803)
  - Packages installed/removed via DNF API are logged into dnf.log (RhBug:1855158)
  - Support comps groups in history redo (RhBug:1657123,1809565,1809639)
  - Support comps groups in history rollback (RhBug:1657123,1809565,1809639)
  - Support comps groups in history undo (RhBug:1657123,1809565,1809639)
  - New optional parameter for filter_modules enables following modular obsoletes based on a config option module_obsoletes
  - Add get_header() method to the Package class (RhBug:1876606)

- Bug fixes:
  - Fix documentation of globs not supporting curly brackets (RhBug:1913418)

Bugs fixed in 4.6.0:

* :rhbug:`1657123`
* :rhbug:`1809639`
* :rhbug:`1913418`
* :rhbug:`1865803`
* :rhbug:`1904490`
* :rhbug:`1847340`
* :rhbug:`1814831`
* :rhbug:`1895059`
* :rhbug:`1855158`
* :rhbug:`1873146`
* :rhbug:`1809565`
* :rhbug:`1876606`

===================
4.5.2 Release Notes
===================

- Change behaviour of Package().from_repo

Bugs fixed in 4.5.2:


===================
4.5.1 Release Notes
===================

- Add a get_current() method to SwdbInterface
- Add `from_repo` attribute for Package class (RhBug:1898968,1879168)
- Correct description of Package().reponane attribute
- Add unittest for new API
- Make rotated log file (mode, owner, group) match previous log settings (RhBug:1894344)
- [doc] Improve description of modular filtering
- [doc] add documentation for from_repo
- [doc] deprecated alias for dnf repoquery --deplist <deplist_option-label>

- New features:
  - New config option module_allow_stream_switch allows switching enabled streams

Bugs fixed in 4.5.1:

* :rhbug:`1894344`
* :rhbug:`1898548`
* :rhbug:`1879168`
* :rhbug:`1898968`

===================
4.4.2 Release Notes
===================

- spec: Fix building with new cmake macros (backport from downstream)
- Warn about key retrieval over http:
- Fix --setopt=cachedir writing outside of installroot
- Add vendor to dnf API (RhBug:1876561)
- Add allow_vendor_change option (RhBug:1788371) (RhBug:1788371)

Bugs fixed in 4.4.2:

* :rhbug:`1876561`
* :rhbug:`1788371`

===================
4.4.0 Release Notes
===================

- Handle empty comps group name (RhBug:1826198)
- Remove dead history info code (RhBug:1845800)
- Improve command emmitter in dnf-automatic
- Enhance --querytags and --qf help output
- [history] add option --reverse to history list (RhBug:1846692)
- Add logfilelevel configuration (RhBug:1802074)
- Don't turn off stdout/stderr logging longer than necessary (RhBug:1843280)
- Mention the date/time that updates were applied
- [dnf-automatic] Wait for internet connection (RhBug:1816308)
- [doc] Enhance repo variables documentation (RhBug:1848161,1848615)
- Add librepo logger for handling messages from librepo (RhBug:1816573)
- [doc] Add package-name-spec to the list of possible specs
- [doc] Do not use <package-nevr-spec>
- [doc] Add section to explain -n, -na and -nevra suffixes
- Add alias 'ls' for list command
- README: Reference Fedora Weblate instead of Zanata
- remove log_lock.pid after reboot(Rhbug:1863006)
- comps: Raise CompsError when removing a non-existent group
- Add methods for working with comps to RPMTransactionItemWrapper
- Implement storing and replaying a transaction
- Log failure to access last makecache time as warning
- [doc] Document Substitutions class
- Dont document removed attribute ``reports`` for get_best_selector
- Change the debug log timestamps from UTC to local time

Bugs fixed in 4.4.0:

* :rhbug:`1698145`
* :rhbug:`1848161`
* :rhbug:`1846692`
* :rhbug:`1857029`
* :rhbug:`1853349`
* :rhbug:`1848615`
* :rhbug:`1845800`
* :rhbug:`1872586`
* :rhbug:`1839951`
* :rhbug:`1843280`
* :rhbug:`1862739`
* :rhbug:`1816308`
* :rhbug:`1802074`
* :rhbug:`1858491`
* :rhbug:`1816573`

====================
4.2.23 Release Notes
====================

- Fix behavior of install-n, autoremove-n, remove-n, repoquery-n
- Fix behavior of localinstall and list-updateinfo aliases
- Add updated field to verbose output of updateinfo list (RhBug: 1801092)
- Add comment option to transaction (RhBug:1773679)
- Add new API for handling gpg signatures (RhBug:1339617)
- Verify GPG signatures when running dnf-automatic (RhBug:1793298)
- Fix up Conflicts: on python-dnf-plugins-extras
- [doc] Move yum-plugin-post-transaction-actions to dnf-plugins-core
- Remove args "--set-enabled", "--set-disabled" from DNF (RhBug:1727882)
- Search command is now alphabetical (RhBug:1811802)
- Fix downloading packages with full URL as their location
- repo: catch libdnf.error.Error in addition to RuntimeError in load() (RhBug:1788182)
- History table to max size when redirect to file (RhBug:1786335,1786316)

Bugs fixed in 4.2.23:

* :rhbug:`1339617`
* :rhbug:`1801092`
* :rhbug:`1727882`
* :rhbug:`1786316`
* :rhbug:`1773679`
* :rhbug:`1793298`
* :rhbug:`1788182`
* :rhbug:`1811802`
* :rhbug:`1813244`
* :rhbug:`1786335`

====================
4.2.21 Release Notes
====================

- Fix completion helper if solv files not in roon cache (RhBug:1714376)
- Add bash completion for 'dnf module' (RhBug:1565614)
- Check command no longer reports  missing %pre and %post deps (RhBug:1543449)
- Check if arguments can be encoded in 'utf-8'
- [doc] Remove incorrect information about includepkgs (RhBug:1813460)
- Fix crash with "dnf -d 6 repolist" (RhBug:1812682)
- Do not print the first empty line for repoinfo
- Redirect logger and repo download progress when --verbose
- Respect repo priority when listing packages (RhBug:1800342)
- [doc] Document that list and info commands respect repo priority
- [repoquery] Do not protect running kernel for --unsafisfied (RhBug:1750745)
- Remove misleading green color from the "broken dependencies" lines (RhBug:1814192)
- [doc] Document color options

Bugs fixed in 4.2.21:

* :rhbug:`1814192`
* :rhbug:`1809600`
* :rhbug:`1565614`
* :rhbug:`1812682`
* :rhbug:`1750745`
* :rhbug:`1813460`
* :rhbug:`1543449`
* :rhbug:`1800342`
* :rhbug:`1812693`

====================
4.2.19 Release Notes
====================

- match RHEL behavior for CentOS and do not require deltarpm
- List arguments: only first empty value is used (RhBug:1788154)
- Report missing profiles or default as broken module (RhBug:1790967)
- repoquery: fix rich deps matching by using provide expansion from libdnf (RhBug:1534123)
- [documentation] repoquery --what* with  multiple arguments (RhBug:1790262)
- Format history table to use actual terminal width (RhBug:1786316)
- Update `dnf alias` documentation
- Handle custom exceptions from libdnf
- Fix _skipped_packages to return only skipped (RhBug:1774617)
- Add setter for tsi.reason
- Add new hook for commands: Run_resolved
- Add doc entry: include url (RhBug 1786072)
- Clean also .yaml repository metadata
- New API function base.setup_loggers() (RhBug:1788212)
- Use WantedBy=timers.target for all dnf timers (RhBug:1798475)

Bugs fixed in 4.2.19:

* :rhbug:`1798475`
* :rhbug:`1788212`
* :rhbug:`1677774`
* :rhbug:`1786316`
* :rhbug:`1790967`
* :rhbug:`1774617`
* :rhbug:`1534123`
* :rhbug:`1790262`
* :rhbug:`1788154`

====================
4.2.18 Release Notes
====================

- [doc] Remove note about user-agent whitelist
- Do a substitution of variables in repo_id (RhBug:1748841)
- Respect order of config files in aliases.d (RhBug:1680489)
- Unify downgrade exit codes with upgrade (RhBug:1759847)
- Improve help for 'dnf module' command (RhBug:1758447)
- Add shell restriction for local packages (RhBug:1773483)
- Fix detection of the latest module (RhBug:1781769)
- Document the retries config option only works for packages (RhBug:1783041)
- Sort packages in transaction output by nevra (RhBug:1773436)
- Honor repo priority with check-update (RhBug:1769466)
- Strip '\' from aliases when processing (RhBug:1680482)
- Print the whole alias definition in case of infinite recursion (RhBug:1680488)
- Add support of commandline packages by repoquery (RhBug:1784148)
- Running with tsflags=test doesn't update log files
- Restore functionality of remove --oldinstallonly
- Allow disabling individual aliases config files (RhBug:1680566)

Bugs fixed in 4.2.18:

* :rhbug:`1773483`
* :rhbug:`1758447`
* :rhbug:`1748841`
* :rhbug:`1679008`
* :rhbug:`1680482`
* :rhbug:`1680566`
* :rhbug:`1784148`
* :rhbug:`1680488`
* :rhbug:`1759847`
* :rhbug:`1773436`
* :rhbug:`1783041`
* :rhbug:`1680489`
* :rhbug:`1781769`

====================
4.2.17 Release Notes
====================

- Enable versionlock for check-update command (RhBug:1750620)
- Add error message when no active modules matched (RhBug:1696204)
- Log mirror failures as warning when repo load fails (RhBug:1713627)
- dnf-automatic: Change all systemd timers to a fixed time of day (RhBug:1754609)
- DNF can use config from the remote location (RhBug:1721091)
- [doc] update reference to plugin documentation (RhBug:1706386)
- [yum compatibility] Report all packages in repoinfo
- [doc] Add definition of active/inactive module stream
- repoquery: Add a switch to disable modular excludes
- Report more informative messages when no match for argument (RhBug:1709563)
- [doc] Add description of excludes in dnf
- Report more descriptive message when removed package is excluded
- Add module repoquery command
- Fix assumptions about ARMv8 and the way the rpm features work (RhBug:1691430)
- Add Requires information into module info commands
- Enhance inheritance of transaction reasons (RhBug:1672618,1769788)

Bugs fixed in 4.2.17:

* :rhbug:`1696204`
* :rhbug:`1709563`
* :rhbug:`1721091`
* :rhbug:`1769788`
* :rhbug:`1706386`
* :rhbug:`1750620`
* :rhbug:`1713627`
* :rhbug:`1672618`
* :rhbug:`1754609`
* :rhbug:`1691430`

====================
4.2.16 Release Notes
====================

- Make DNF compatible with FIPS mode (RhBug:1762032)
- Return always alphabetically sorted modular profiles
- Revert "Fix messages for starting and failing scriptlets"

====================
4.2.15 Release Notes
====================

- Fix downloading local packages into destdir (RhBug:1727137)
- Report skipped packages with identical nevra only once (RhBug:1643109)
- Restore functionality of dnf remove --duplicates (RhBug:1674296)
- Improve API documentation
- Document NEVRA parsing in the man page
- Do not wrap output when no terminal (RhBug:1577889)
- Allow to ship alternative dnf.conf (RhBug:1752249)
- Don't check if repo is expired if it doesn't have loaded metadata (RhBug:1745170)
- Remove duplicate entries from "dnf search" output (RhBug:1742926)
- Set default value of repo name attribute to repo id (RhBug:1669711)
- Allow searching in disabled modules using "dnf module provides" (RhBug:1629667)
- Group install takes obsoletes into account (RhBug:1761137)
- Improve handling of vars
- Do not load metadata for repolist commands (RhBug:1697472,1713055,1728894)
- Fix messages for starting and failing scriptlets (RhBug:1724779)
- Don't show older install-only pkgs updates in updateinfo (RhBug:1649383,1728004)
- Add --ids option to the group command (RhBug:1706382)
- Add --with_cve and --with_bz options to the updateinfo command (RhBug:1750528)

Bugs fixed in 4.2.15:

* :rhbug:`1738837`
* :rhbug:`1674296`
* :rhbug:`1577889`
* :rhbug:`1669711`
* :rhbug:`1643109`
* :rhbug:`1649383`
* :rhbug:`1666236`
* :rhbug:`1728894`
* :rhbug:`1727137`
* :rhbug:`1689645`
* :rhbug:`1742926`
* :rhbug:`1761137`
* :rhbug:`1706382`
* :rhbug:`1761518`
* :rhbug:`1752249`
* :rhbug:`1760937`
* :rhbug:`1713055`
* :rhbug:`1724779`
* :rhbug:`1745170`
* :rhbug:`1750528`

====================
4.2.11 Release Notes
====================

- Improve modularity documentation (RhBug:1730162,1730162,1730807,1734081)
- Fix detection whether system is running on battery (used by metadata caching timer) (RhBug:1498680)
- New repoquery queryformat: %{reason}
- Print rpm errors during test transaction (RhBug:1730348) 
- Fix: --setopt and repo with dots
- Fix incorrectly marked profile and stream after failed rpm transaction check (RhBug:1719679)
- Show transaction errors inside dnf shell (RhBug:1743644)
- Don't reinstall modified packages with the same NEVRA (RhBug:1644241)
- dnf-automatic now respects versionlock excludes (RhBug:1746562)

Bugs fixed in 4.2.11:

* :rhbug:`1498680`
* :rhbug:`1730348`
* :rhbug:`1719679`
* :rhbug:`1601741`
* :rhbug:`1665636`
* :rhbug:`1739457`
* :rhbug:`1715807`
* :rhbug:`1734081`
* :rhbug:`1739773`
* :rhbug:`1730807`
* :rhbug:`1728252`
* :rhbug:`1746562`
* :rhbug:`1730162`
* :rhbug:`1743644`
* :rhbug:`1737201`
* :rhbug:`1689645`
* :rhbug:`1741381`

===================
4.2.9 Release Notes
===================

- Prevent printing empty Error Summary (RhBug: 1690414)
- [doc] Add user_agent and countme options

===================
4.2.8 Release Notes
===================

- Enhance synchronization of rpm transaction to swdb
- Accept multiple specs in repoquery options (RhBug:1667898)
- Prevent switching modules in all cases (RhBug:1706215)
- [history] Don't store failed transactions as succeeded
- [history] Do not require root for informative commands
- [dnssec] Fix UnicodeWarning when using new rpm (RhBug:1699650)
- Print rpm error messages during transaction (RhBug:1677199)
- Report missing default profile as an error (RhBug:1669527)
- Apply excludes before modular excludes (RhBug:1709453)
- Improve help for command line arguments (RhBug:1659328)
- [doc] Describe a behavior when plugin is removed (RhBug:1700741)
- Add new modular API method ModuleBase.get_modules
- Mark features used by ansible, anaconda and subscription-manager as an API

Bugs fixed in 4.2.8:

* :rhbug:`1630113`
* :rhbug:`1653736`
* :rhbug:`1669527`
* :rhbug:`1661814`
* :rhbug:`1667898`
* :rhbug:`1673075`
* :rhbug:`1677199`
* :rhbug:`1699650`
* :rhbug:`1700741`
* :rhbug:`1706215`
* :rhbug:`1709453`

===================
4.2.7 Release Notes
===================

- Set default to skip_if_unavailable=false (RhBug:1679509)
- Fix package reinstalls during yum module remove (RhBug:1700529)
- Fail when "-c" option is given nonexistent file (RhBug:1512457)
- Reuse empty lock file instead of stopping dnf (RhBug:1581824)
- Propagate comps 'default' value correctly (RhBug:1674562)
- Better search of provides in /(s)bin/ (RhBug:1657993)
- Add detection for armv7hcnl (RhBug:1691430)
- Fix group install/upgrade when group is not available (RhBug:1707624)
- Report not matching plugins when using --enableplugin/--disableplugin
  (RhBug:1673289) (RhBug:1467304)
- Add support of modular FailSafe (RhBug:1623128)
- Replace logrotate with build-in log rotation for dnf.log and dnf.rpm.log
  (RhBug:1702690)

Bugs fixed in 4.2.7:

* :rhbug:`1702690`
* :rhbug:`1672649`
* :rhbug:`1467304`
* :rhbug:`1673289`
* :rhbug:`1674562`
* :rhbug:`1581824`
* :rhbug:`1709783`
* :rhbug:`1512457`
* :rhbug:`1673913`

===================
4.2.6 Release Notes
===================

- librepo: Turn on debug logging only if debuglevel is greater than 2 (RhBug:1355764,1580022)
- Fix issues with terminal hangs when attempting bash completion (RhBug:1702854)
- Rename man page from dnf.automatic to dnf-automatic to match command name
- [provides] Enhanced detecting of file provides (RhBug:1702621)
- [provides] Sort the output packages alphabetically

Bugs fixed in 4.2.6:

* :rhbug:`1355764`
* :rhbug:`1580022`
* :rhbug:`1702621`
* :rhbug:`1702854`

===================
4.2.5 Release Notes
===================

- Fix multilib obsoletes (RhBug:1672947)
- Do not remove group package if other packages depend on it
- Remove duplicates from "dnf list" and "dnf info" outputs
- Installroot now requires absolute path
- Fix the installation of completion_helper.py
- Allow globs in setopt in repoid part
- Fix formatting of message about free space required
- [doc] Add info of relation update_cache with fill_sack (RhBug:1658694)
- Fix installation failure when duplicate RPMs are specified (RhBug:1687286)
- Add command abbreviations (RhBug:1634232)
- Allow plugins to terminate dnf (RhBug:1701807)

Bugs fixed in 4.2.5:

* :rhbug:`1701807`
* :rhbug:`1634232`
* :rhbug:`1687286`
* :rhbug:`1658694`
* :rhbug:`1672947`

===================
4.2.2 Release Notes
===================

- [conf] Use environment variables prefixed with ``DNF_VAR_``
- Enhance documentation of --whatdepends option (RhBug:1687070)
- Allow adjustment of repo from --repofrompath (RhBug:1689591)
- Document cachedir option (RhBug:1691365)
- Retain order of headers in search results (RhBug:1613860)
- Solve traceback with the "dnf install @module" (RhBug:1688823)
- Build "yum" instead of "dnf-yum" on Fedora 31

Bugs fixed in 4.2.2:

* :rhbug:`1689591`
* :rhbug:`1687070`

===================
4.2.1 Release Notes
===================

* Do not allow direct module switch (RhBug:1669491)
* Use improved config parser that preserves order of data
* Fix ``alias list`` command (RhBug:1666325)
* Postpone yum conflict to F31
* Update documentation: implemented plugins; options; deprecated commands (RhBug:1670835,1673278) 
* Support zchunk (".zck") compression
* Fix behavior  of ``--bz`` option when specifying more values
* Follow RPM security policy for package verification
* Update modules regardless of installed profiles
* Add protection of yum package (RhBug:1639363)
* Fix ``list --showduplicates`` (RhBug:1655605)

Bugs fixed in 4.2.1:

* :rhbug:`1655605`
* :rhbug:`1669247`
* :rhbug:`1670835`
* :rhbug:`1673278`
* :rhbug:`1677640`
* :rhbug:`1597182`
* :rhbug:`1666325`
* :rhbug:`1678689`
* :rhbug:`1669491`

===================
4.1.0 Release Notes
===================

* Allow to enable modules that break default modules (RhBug:1648839)
* Enhance documentation - API examples
* Add best as default behavior (RhBug:1670776,1671683)
* Add --nobest option

Bugs fixed in 4.1.0:

* :rhbug:`1585509`
* :rhbug:`1672432`
* :rhbug:`1509393`
* :rhbug:`1667423`
* :rhbug:`1656726`
* :rhbug:`1671683`
* :rhbug:`1667426`

====================
4.0.10 Release Notes
====================

* Updated difference YUM vs. DNF for yum-updateonboot
* Added new command ``dnf alias [options] [list|add|delete] [<name>...]`` to allow the user to
  define and manage a list of aliases
* Enhanced documentation
* Unifying return codes for remove operations
* [transaction] Make transaction content available for commands
* Triggering transaction hooks if no transaction (RhBug:1650157)
* Add hotfix packages to install pool (RhBug:1654738)
* Report group operation in transaction table
* [sack] Change algorithm to calculate rpmdb_version

Bugs fixed in 4.0.10:

* :rhbug:`1654738`
* :rhbug:`1495482`

===================
4.0.9 Release Notes
===================

* Added :meth:`dnf.repo.Repo.get_http_headers`
* Added :meth:`dnf.repo.Repo.set_http_headers`
* Added :meth:`dnf.repo.Repo.add_metadata_type_to_download`
* Added :meth:`dnf.repo.Repo.get_metadata_path`
* Added :meth:`dnf.repo.Repo.get_metadata_content`
* Added --changelogs option for check-update command
* [module] Add information about active modules
* Hide messages created only for logging
* Enhanced --setopt option
* [module] Fix dnf remove @<module>
* [transaction] Make transaction content available for plugins

Bugs fixed in 4.0.9:

* :rhbug:`1541832`
* :rhbug:`1642796`
* :rhbug:`1637148`
* :rhbug:`1639998`
* :rhbug:`1615164`
* :rhbug:`1636480`

===================
4.0.4 Release Notes
===================

* Add dnssec extension
* Set termforce to AUTO to automatically detect if stdout is terminal
* Repoquery command accepts --changelogs option (RhBug:1483458)
* Calculate sack version from all installed packages (RhBug:1624291)
* [module] Allow to enable module dependencies (RhBug:1622566)

Bugs fixed in 4.0.4:

* :rhbug:`1508649`
* :rhbug:`1590690`
* :rhbug:`1624291`
* :rhbug:`1631217`
* :rhbug:`1489308`
* :rhbug:`1625879`
* :rhbug:`1483458`
* :rhbug:`1497171`
* :rhbug:`1620242`

===================
3.6.1 Release Notes
===================

* [module] Improved module commands list, info
* [module] Reports error from module solver

Bugs fixed in 3.6.1:

* :rhbug:`1626011`
* :rhbug:`1631458`
* :rhbug:`1305340`
* :rhbug:`1305340`
* :rhbug:`1623866`
* :rhbug:`1600444`
* :rhbug:`1628056`

===================
3.5.1 Release Notes
===================

* [module] Fixed list and info subcommands

===================
3.5.0 Release Notes
===================

* New implementation of modularity

===================
3.0.2 Release Notes
===================

* Add limited compatibility with dnf-2.0 (constants)

===================
3.0.1 Release Notes
===================

* Support of MODULES - new DNF command `module`
* :attr:`dnf.conf.Conf.proxy_auth_method`
* New repoquery option `--depends` and `--whatdepends`
* Enhanced support of variables
* Enhanced documentation

Bugs fixed in 3.0.1:

* :rhbug:`1565599`
* :rhbug:`1508839`
* :rhbug:`1506486`
* :rhbug:`1506475`
* :rhbug:`1505577`
* :rhbug:`1505574`
* :rhbug:`1505573`
* :rhbug:`1480481`
* :rhbug:`1496732`
* :rhbug:`1497272`
* :rhbug:`1488100`
* :rhbug:`1488086`
* :rhbug:`1488112`
* :rhbug:`1488105`
* :rhbug:`1488089`
* :rhbug:`1488092`
* :rhbug:`1486839`
* :rhbug:`1486839`
* :rhbug:`1486827`
* :rhbug:`1486816`
* :rhbug:`1565647`
* :rhbug:`1583834`
* :rhbug:`1576921`
* :rhbug:`1270295`
* :rhbug:`1361698`
* :rhbug:`1369847`
* :rhbug:`1368651`
* :rhbug:`1563841`
* :rhbug:`1387622`
* :rhbug:`1575998`
* :rhbug:`1577854`
* :rhbug:`1387622`
* :rhbug:`1542416`
* :rhbug:`1542416`
* :rhbug:`1496153`
* :rhbug:`1568366`
* :rhbug:`1539803`
* :rhbug:`1552576`
* :rhbug:`1545075`
* :rhbug:`1544359`
* :rhbug:`1547672`
* :rhbug:`1537957`
* :rhbug:`1542920`
* :rhbug:`1507129`
* :rhbug:`1512956`
* :rhbug:`1512663`
* :rhbug:`1247083`
* :rhbug:`1247083`
* :rhbug:`1247083`
* :rhbug:`1519325`
* :rhbug:`1492036`
* :rhbug:`1391911`
* :rhbug:`1391911`
* :rhbug:`1479330`
* :rhbug:`1505185`
* :rhbug:`1305232`

===================
2.7.5 Release Notes
===================

* Improved performance for excludes and includes handling
* Fixed problem of handling checksums for local repositories
* Fix traceback when using dnf.Base.close()

Bugs fixed in 2.7.5:

* :rhbug:`1502106`
* :rhbug:`1500361`
* :rhbug:`1503575`

===================
2.7.4 Release Notes
===================

* Enhanced performance for excludes and includes handling
* Solved memory leaks at time of closing of dnf.Base()

Bugs fixed in 2.7.4:

* :rhbug:`1480979`
* :rhbug:`1461423`
* :rhbug:`1499564`
* :rhbug:`1499534`
* :rhbug:`1499623`

===================
2.7.3 Release Notes
===================

Bugs fixed in 2.7.3:

* :rhbug:`1472847`
* :rhbug:`1498426`
* :rhbug:`1427144`

===================
2.7.2 Release Notes
===================

API additions in 2.7.2:

* Added new option ``--comment=<comment>`` that adds a comment to transaction in history
* :meth:`dnf.Base.pre_configure_plugin` configure plugins by running their pre_configure() method
* Added pre_configure() method for plugins and commands to configure dnf before repos are loaded

Bugs fixed in 2.7.2:

* :rhbug:`1421478`
* :rhbug:`1491560`
* :rhbug:`1465292`
* :rhbug:`1279001`
* :rhbug:`1212341`
* :rhbug:`1299482`
* :rhbug:`1192811`
* :rhbug:`1288845`
* :rhbug:`1237349`
* :rhbug:`1470050`
* :rhbug:`1347927`
* :rhbug:`1478115`
* :rhbug:`1461171`
* :rhbug:`1495116`
* :rhbug:`1448874`

===================
2.6.3 Release Notes
===================

API additions in 2.6.3:

* Added auto substitution for all variables used for repo creation by :meth:`dnf.repodict.RepoDict.add_new_repo`
* Added description of ``--downloaddir=<path>`` dnf option

Bugs fixed in 2.6.3:

* :rhbug:`1476215`
* :rhbug:`1473964`
* :rhbug:`1359482`
* :rhbug:`1476834`
* :rhbug:`1244755`
* :rhbug:`1476748`
* :rhbug:`1476464`
* :rhbug:`1464192`
* :rhbug:`1463107`
* :rhbug:`1426196`
* :rhbug:`1457507`

===================
2.6.2 Release Notes
===================

API additions in 2.6.2:

* :attr:`dnf.conf.Conf.basearch`
* :attr:`dnf.conf.Conf.arch`
* :attr:`dnf.conf.Conf.ignorearch`
* Introduced new configuration option ``autocheck_running_kernel``
* :meth:`dnf.subject.Subject.get_best_selector` can use three additional key words: ``obsoletes``, ``reports``, and ``reponame``.

From commandline it is possible to use new option ``--noautoremove`` to disable removal of dependencies that are no longer used.

Bugs fixed in 2.6.2:

* :rhbug:`1279001`
* :rhbug:`1397848`
* :rhbug:`1361424`
* :rhbug:`1387925`
* :rhbug:`1332099`
* :rhbug:`1470116`
* :rhbug:`1161950`
* :rhbug:`1320254`
* :rhbug:`1424723`
* :rhbug:`1462486`
* :rhbug:`1314405`
* :rhbug:`1457368`
* :rhbug:`1339280`
* :rhbug:`1138978`
* :rhbug:`1423472`
* :rhbug:`1427365`
* :rhbug:`1398871`
* :rhbug:`1432312`

===================
2.5.1 Release Notes
===================

API additions in 2.5.1:

* :meth:`dnf.Plugin.pre_transaction` is a hook that is called just before transaction execution.
* :meth:`dnf.subject.Subject.get_nevra_possibilities` returns generator for every possible nevra.

Bugs fixed in 2.5.1:

* :rhbug:`1456419`
* :rhbug:`1445021`
* :rhbug:`1400714`
* :rhbug:`1250702`
* :rhbug:`1381988`
* :rhbug:`1397848`
* :rhbug:`1321407`
* :rhbug:`1291867`
* :rhbug:`1372895`
* :rhbug:`1444751`

===================
2.5.0 Release Notes
===================

API additions in 2.5.0:

:meth:`dnf.callback.DownloadProgress.start` can use one additional key word ``total_drpms``.

Bugs fixed in 2.5.0:

* :rhbug:`1350546`
* :rhbug:`1449618`
* :rhbug:`1270451`
* :rhbug:`1254966`
* :rhbug:`1426787`
* :rhbug:`1293983`
* :rhbug:`1370062`
* :rhbug:`1293067`
* :rhbug:`1393814`
* :rhbug:`1398040`
* :rhbug:`1342157`
* :rhbug:`1379906`
* :rhbug:`1198975`

===================
2.4.1 Release Notes
===================

DNF command additions in 2.4.1:

* ``dnf [options] repoquery --userinstalled`` limit the resulting set only to packages installed by user.

Bugs fixed in 2.4.1:

* :rhbug:`1446756`
* :rhbug:`1446432`
* :rhbug:`1446641`
* :rhbug:`1278124`
* :rhbug:`1301868`

===================
2.4.0 Release Notes
===================

API additions in 2.4.0:

* :meth:`dnf.subject.Subject.get_best_query` can use two additional key words: ``with_nevra``, and ``with_filenames``.
* Added description of :attr:`dnf.repo.Repo.cost`
* Added description of :attr:`dnf.repo.Repo.excludepkgs`
* Added description of :attr:`dnf.repo.Repo.includepkgs`

DNF command additions in 2.4.0:

* ``--enableplugin=<plugin names>`` :doc:`command line argument <command_ref>` enable the listed plugins specified by names or globs.
* ``--releasever=<release>`` :doc:`command line argument <command_ref>` now autodetect releasever in installroot from host if ``/`` value is used as ``<release>``.

Bugs fixed in 2.4.0:

* :rhbug:`1302935`
* :rhbug:`1248684`
* :rhbug:`1441636`
* :rhbug:`1438438`
* :rhbug:`1256313`
* :rhbug:`1161950`
* :rhbug:`1421244`

===================
2.3.0 Release Notes
===================

API additions in 2.3.0:

* :meth:`dnf.package.Package.remote_location` returns location from where the package can be downloaded from.

DNF command additions in 2.3.0:

* ``dnf [options] repoquery --whatconflicts <capability>`` limit the resulting set only to packages that conflict ``<capability>``.
* ``dnf [options] repoquery --whatobsoletes <capability>`` limit the resulting set only to packages that obsolete ``<capability>``.
* ``dnf [options] repoquery --location`` show a location where the package could be downloaded from.
* ``dnf [options] repoquery --nvr`` show found packages in format name-version-release.
* ``dnf [options] repoquery --nevra`` show found packages in format name-epoch:version-release.architecture (default).
* ``dnf [options] repoquery --envra`` show found packages in format epoch:name-version-release.architecture.
* ``dnf [options] repoquery --recursive`` query packages recursively. Can be used with ``--whatrequires <REQ>`` (optionally with --alldeps, but it has no effect with --exactdeps), or with ``--requires <REQ> --resolve``.

Bugs fixed in 2.3.0:

* :rhbug:`1290137`
* :rhbug:`1349314`
* :rhbug:`1247122`
* :rhbug:`1298717`

===================
2.2.0 Release Notes
===================

API additions in 2.2.0:

* :meth:`dnf.callback.TransactionProgress.progress` has new actions: TRANS_PREPARATION, TRANS_POST, and PKG_SCRIPTLET.

Bugs fixed in 2.2.0:

* :rhbug:`1411432`
* :rhbug:`1406130`
* :rhbug:`1411423`
* :rhbug:`1369212`

===================
2.1.1 Release Notes
===================

Bugs fixed in 2.1.1:

* :rhbug:`1417542`
* :rhbug:`1401446`
* :rhbug:`1416699`
* :rhbug:`1427132`
* :rhbug:`1397047`
* :rhbug:`1379628`
* :rhbug:`1424939`
* :rhbug:`1396992`
* :rhbug:`1412970`

===================
2.1.0 Release Notes
===================

API additions in 2.1.0:

* :meth:`dnf.Base.update_cache` downloads and caches in binary format metadata for all known repos.

Bugs fixed in 2.1.0:

* :rhbug:`1421835`
* :rhbug:`1415711`
* :rhbug:`1417627`

===================
2.0.1 Release Notes
===================

API changes in 2.0.1:

* :meth:`dnf.Base.package_downgrade` now accept keyword strict to ignore problems with dep-solving

API additions in 2.0.1:

* :meth:`dnf.Base.autoremove` removes all 'leaf' packages from the system that were originally installed as dependencies
* :meth:`dnf.cli.Cli.redirect_logger` changes minimal logger level for terminal output to stdout and stderr

DNF command additions in 2.0.1:

* ``dnf [options] shell [filename]`` opens an interactive shell for conducting multiple commands during a single execution of DNF
* ``dnf [options] swap <remove-spec> <install-spec>`` removes spec and install spec in one transaction

Bugs fixed in 2.0.1:

* :rhbug:`1409361`
* :rhbug:`1414512`
* :rhbug:`1238808`
* :rhbug:`1386085`
* :rhbug:`1286553`
* :rhbug:`1337731`
* :rhbug:`1336879`
* :rhbug:`1173349`
* :rhbug:`1329617`
* :rhbug:`1283255`
* :rhbug:`1369411`
* :rhbug:`1243393`
* :rhbug:`1243393`
* :rhbug:`1411349`
* :rhbug:`1345976`
* :rhbug:`1369212`
* :rhbug:`1349247`
* :rhbug:`1403930`
* :rhbug:`1403465`
* :rhbug:`1110780`
* :rhbug:`1405333`
* :rhbug:`1254879`

===================
2.0.0 Release Notes
===================

List of all incompatible changes can be found at: :doc:`dnf-1 vs dnf-2 <dnf-1_vs_dnf-2>`

API changes in 2.0.0:

* :meth:`dnf.Base.add_remote_rpms` now suppresses any error if :attr:`strict` equals to ``False``.
* :meth:`dnf.Base.read_comps` now limits results to system basearch if :attr:`arch_filter` equals to ``True``.
* :meth:`dnf.cli.Cli.configure` now doesn't take any additional arguments.
* :meth:`dnf.cli.Cli.run` now doesn't take any additional arguments.
* :meth:`dnf.Plugin.read_config` now doesn't take any name of config file.
* :meth:`dnf.Repo.__init__` now takes `parent_conf` argument which is an instance of :class:`dnf.conf.Conf` holding main dnf configuration instead of `cachedir` path.
* ``exclude`` and ``include`` configuration options change to ``excludepkgs`` and ``includepkgs``.

API additions in 2.0.0:

* :meth:`dnf.Base.init_plugins` initializes plugins. It is possible to disable some plugins by passing the list of their name patterns to :attr:`disabled_glob`.
* :meth:`dnf.Base.configure_plugins` configures plugins by running their :meth:`configure` method.
* :meth:`dnf.Base.urlopen` opens the specified absolute ``url`` and returns a file object which respects proxy setting even for non-repo downloads
* Introduced new configuration options: ``check_config_file_age``, ``clean_requirements_on_remove``, ``deltarpm_percentage``, ``exit_on_lock``, ``get_reposdir``, ``group_package_types``, ``installonlypkgs``, ``keepcache``, ``protected_packages``, ``retries``, ``type``, and ``upgrade_group_objects_upgrade``. For detailed description see: :doc:`DNF API <api_conf>`.
* Introduced new configuration methods: :meth:`dump` and :meth:`write_raw_configfile`. For detailed description see: :doc:`DNF API <api_conf>`.
* Introduced :class:`dnf.package.Package` attributes :attr:`debug_name`, :attr:`downloadsize`, :attr:`source_debug_name` and :attr:`source_name`. For detailed description see: :doc:`DNF Package API <api_package>`.
* :meth:`dnf.query.Query.extras` returns a new query that limits the result to installed packages that are not present in any repo.
* :meth:`dnf.repo.Repo.enable_debug_repos` enables debug repos corresponding to already enabled binary repos.
* :meth:`dnf.repo.Repo.enable_source_repos` enables source repos corresponding to already enabled binary repos.
* :meth:`dnf.repo.Repo.dump` prints repository configuration, including inherited values.
* :meth:`dnf.query.Query.filter` now accepts optional argument `pkg`.

DNF command changes in 2.0.0:

* ``dnf [options] group install [with-optional] <group-spec>...`` changes to ``dnf [options] group install [--with-optional] <group-spec>...``.
* ``dnf [options] list command [<package-name-specs>...]`` changes to `dnf [options] list --command [<package-name-specs>...]``.
* ``dnf [options] makecache timer`` changes to ``dnf [options] makecache --timer``.
* ``dnf [options] repolist [enabled|disabled|all]`` changes to ``dnf [options] repolist [--enabled|--disabled|--all]``.
* ``dnf [options] repository-packages <repoid> info command [<package-name-spec>...]`` changes to ``dnf [options] repository-packages <repoid> info --command [<package-name-spec>...]``.
* ``dnf repoquery --duplicated`` changes to ``dnf repoquery --duplicates``.
* ``dnf [options] search [all] <keywords>...`` changes to ``dnf [options] search [--all] <keywords>...``.
* ``dnf [options] updateinfo [<availability>] [<spec>...]`` changes to ``dnf [options] updateinfo [--summary|--list|--info] [<availability>] [<spec>...]``.
* ``--disablerepo`` :doc:`command line argument <command_ref>` is mutually exclusive with ``--repo``.
* ``--enablerepo`` :doc:`command line argument <command_ref>` now appends repositories.
* ``--installroot`` :doc:`command line argument <command_ref>`. For detailed description see: :doc:`DNF command API <command_ref>`.
* ``--releasever`` :doc:`command line argument <command_ref>` now doesn't detect release number from running system.
* ``--repofrompath`` :doc:`command line argument <command_ref>` can now be combined with ``--repo`` instead of ``--enablerepo``.
* Alternative of yum's ``deplist`` changes from ``dnf repoquery --requires`` to ``dnf repoquery --deplist``.
* New systemd units `dnf-automatic-notifyonly`, `dnf-automatic-download`, `dnf-automatic-download` were added for a better customizability of :doc:`dnf-automatic <automatic>`.

DNF command additions in 2.0.0:

* ``dnf [options] remove --duplicates`` removes older version of duplicated packages.
* ``dnf [options] remove --oldinstallonly``removes old installonly packages keeping only ``installonly_limit`` latest versions.
* ``dnf [options] repoquery [<select-options>] [<query-options>] [<pkg-spec>]`` searches the available DNF repositories for selected packages and displays the requested information about them. It is an equivalent of ``rpm -q`` for remote repositories.
* ``dnf [options] repoquery --querytags`` provides list of recognized tags by repoquery option \-\ :ref:`-queryformat <queryformat_repoquery-label>`.
* ``--repo`` :doc:`command line argument <command_ref>` enables just specific repositories by an id or a glob. Can be used multiple times with accumulative effect. It is basically shortcut for ``--disablerepo="*" --enablerepo=<repoid>`` and is mutually exclusive with ``--disablerepo`` option.
* New commands have been introduced: ``check`` and ``upgrade-minimal``.
* New security options introduced: ``bugfix``, ``enhancement``, ``newpackage``, ``security``, ``advisory``, ``bzs``, ``cves``, ``sec-severity`` and ``secseverity``.

Bugs fixed in 2.0.0:

* :rhbug:`1229730`
* :rhbug:`1375277`
* :rhbug:`1384289`
* :rhbug:`1398272`
* :rhbug:`1382224`
* :rhbug:`1177785`
* :rhbug:`1272109`
* :rhbug:`1234930`
* :rhbug:`1341086`
* :rhbug:`1382247`
* :rhbug:`1381216`
* :rhbug:`1381432`
* :rhbug:`1096506`
* :rhbug:`1332830`
* :rhbug:`1348766`
* :rhbug:`1337731`
* :rhbug:`1333591`
* :rhbug:`1314961`
* :rhbug:`1372307`
* :rhbug:`1373108`
* :rhbug:`1148627`
* :rhbug:`1267298`
* :rhbug:`1373591`
* :rhbug:`1230355`
* :rhbug:`1366793`
* :rhbug:`1369411`
* :rhbug:`1366793`
* :rhbug:`1369459`
* :rhbug:`1306096`
* :rhbug:`1368832`
* :rhbug:`1366793`
* :rhbug:`1359016`
* :rhbug:`1365593`
* :rhbug:`1297087`
* :rhbug:`1227053`
* :rhbug:`1356926`
* :rhbug:`1055910`
* :rhbug:`1219867`
* :rhbug:`1226677`
* :rhbug:`1350604`
* :rhbug:`1253120`
* :rhbug:`1158548`
* :rhbug:`1262878`
* :rhbug:`1318852`
* :rhbug:`1327438`
* :rhbug:`1343880`
* :rhbug:`1338921`
* :rhbug:`1284349`
* :rhbug:`1338921`
* :rhbug:`1284349`
* :rhbug:`1306096`
* :rhbug:`1218071`
* :rhbug:`1193823`
* :rhbug:`1246211`
* :rhbug:`1193851`
* :rhbug:`1158548`
* :rhbug:`1215208`
* :rhbug:`1212693`
* :rhbug:`1212341`
* :rhbug:`1306591`
* :rhbug:`1227001`
* :rhbug:`1163028`
* :rhbug:`1279185`
* :rhbug:`1289067`
* :rhbug:`1328674`
* :rhbug:`1380580`
* :rhbug:`1327999`
* :rhbug:`1400081`
* :rhbug:`1293782`
* :rhbug:`1386078`
* :rhbug:`1358245`
* :rhbug:`1243393`
* :rhbug:`1339739`

====================
1.1.10 Release Notes
====================

Fixed unicode handling and fixing other bugs.

Bugs fixed in 1.1.10:

* :rhbug:`1257965`
* :rhbug:`1352130`
* :rhbug:`1343764`
* :rhbug:`1308994`
* :rhbug:`1230183`
* :rhbug:`1295090`
* :rhbug:`1325869`
* :rhbug:`1338046`
* :rhbug:`1214768`
* :rhbug:`1338504`
* :rhbug:`1338564`

===================
1.1.9 Release Notes
===================

From this release if you use any non-API methods warning will be printed and
bugfixes.

Bugs fixed in 1.1.9:

* :rhbug:`1324086`
* :rhbug:`1332012`
* :rhbug:`1292892`
* :rhbug:`1328674`
* :rhbug:`1286556`
* :rhbug:`1245121`

===================
1.1.8 Release Notes
===================

Improvements in documentation, bugfixes, translation updates.

Bugs fixed in 1.1.8:

* :rhbug:`1309408`
* :rhbug:`1209649`
* :rhbug:`1272977`
* :rhbug:`1322226`
* :rhbug:`1315349`
* :rhbug:`1214562`
* :rhbug:`1313215`
* :rhbug:`1306057`
* :rhbug:`1289164`

===================
1.1.7 Release Notes
===================

Added :meth:`dnf.rpm.basearch` method, intended for the detection of CPU base architecture.

The :ref:`group list <grouplist_command-label>` command was enriched with ``installed`` and ``available`` switches.

Documented a standard way of overriding autodetected architectures in :doc:`DNF API <api_conf>`.

Bugs fixed in 1.1.7:

* :rhbug:`1286477`
* :rhbug:`1305356`
* :rhbug:`1258503`
* :rhbug:`1283432`
* :rhbug:`1268818`
* :rhbug:`1306304`
* :rhbug:`1302934`
* :rhbug:`1303149`
* :rhbug:`1302217`

===================
1.1.6 Release Notes
===================

Added support of socks5 proxy.

Bugs fixed in 1.1.6:

* :rhbug:`1291895`
* :rhbug:`1256587`
* :rhbug:`1287221`
* :rhbug:`1277360`
* :rhbug:`1294241`
* :rhbug:`1289166`
* :rhbug:`1294355`
* :rhbug:`1226322`
* :rhbug:`1275878`
* :rhbug:`1239274`

===================
1.1.5 Release Notes
===================

Improved the start-up time of bash completion.

Reviewed documentation.

Bugs fixed in 1.1.5:

* :rhbug:`1286619`
* :rhbug:`1229046`
* :rhbug:`1282250`
* :rhbug:`1265391`
* :rhbug:`1283017`
* :rhbug:`1278592`
* :rhbug:`1260421`
* :rhbug:`1278382`
* :rhbug:`1230820`
* :rhbug:`1280240`

===================
1.1.4 Release Notes
===================

API additions in 1.1.4:

* newly added :meth:`dnf.Query.duplicated`
* extended :meth:`dnf.Query.latest`

Bugs fixed in 1.1.4:

* :rhbug:`1278031`
* :rhbug:`1264032`
* :rhbug:`1209056`
* :rhbug:`1274946`

===================
1.1.3 Release Notes
===================

Now :meth:`dnf.Base.group_install` is able to exclude mandatory packages of the group from transaction.

===================
1.1.2 Release Notes
===================

Implemented :ref:`--downloadonly <downloadonly-label>` command line option.

Bugs fixed in 1.1.2:

* :rhbug:`1262082`
* :rhbug:`1250038`
* :rhbug:`1048433`
* :rhbug:`1259650`
* :rhbug:`1260198`
* :rhbug:`1259657`
* :rhbug:`1254982`
* :rhbug:`1261766`
* :rhbug:`1234491`
* :rhbug:`1256531`
* :rhbug:`1254687`
* :rhbug:`1261656`
* :rhbug:`1258364`

===================
1.1.1 Release Notes
===================

Implemented ``dnf mark`` :doc:`command <command_ref>`.

Bugs fixed in 1.1.1:

* :rhbug:`1249319`
* :rhbug:`1234763`
* :rhbug:`1242946`
* :rhbug:`1225225`
* :rhbug:`1254687`
* :rhbug:`1247766`
* :rhbug:`1125925`
* :rhbug:`1210289`

===================
1.1.0 Release Notes
===================

API additions in 1.1.0:

:meth:`dnf.Base.do_transaction` now accepts multiple displays.

Introduced ``install_weak_deps`` :doc:`configuration <conf_ref>` option.

Implemented ``strict`` :doc:`configuration <conf_ref>` option.

API deprecations in 1.1.0:

* ``dnf.callback.LoggingTransactionDisplay`` is deprecated now. It was considered part of API despite the fact that it has never been documented. Use :class:`dnf.callback.TransactionProgress` instead.

Bugs fixed in 1.1.0

* :rhbug:`1210445`
* :rhbug:`1218401`
* :rhbug:`1227952`
* :rhbug:`1197456`
* :rhbug:`1236310`
* :rhbug:`1219638`
* :rhbug:`1207981`
* :rhbug:`1208918`
* :rhbug:`1221635`
* :rhbug:`1236306`
* :rhbug:`1234639`
* :rhbug:`1244486`
* :rhbug:`1224248`
* :rhbug:`1243501`
* :rhbug:`1225237`

===================
1.0.2 Release Notes
===================

When a transaction is not successfully finished, DNF preserves downloaded packages
until the next successful transaction even if ``keepcache`` option is set to ``False``.

Maximum number of simultaneous package downloads can be adjusted by newly added
``max_parallel_downloads`` :doc:`configuration <conf_ref>` option.

``--repofrompath`` :doc:`command line argument <command_ref>` was introduced for temporary configuration of repositories.

API additions in 1.0.2:

Newly added package attributes: :attr:`dnf.package.Package.obsoletes`,
:attr:`dnf.package.Package.provides` and :attr:`dnf.package.Package.requires`.

:attr:`dnf.package.Query.filter`'s keys ``requires`` and ``provides`` now accepts
list of ``Hawkey.Reldep`` type.

Bugs fixed in 1.0.2:

* :rhbug:`1148630`
* :rhbug:`1176351`
* :rhbug:`1210445`
* :rhbug:`1173107`
* :rhbug:`1219199`
* :rhbug:`1220040`
* :rhbug:`1230975`
* :rhbug:`1232815`
* :rhbug:`1113384`
* :rhbug:`1133979`
* :rhbug:`1238958`
* :rhbug:`1238252`
* :rhbug:`1212320`

===================
1.0.1 Release Notes
===================

DNF follows the Semantic Versioning as defined at `<http://semver.org/>`_.

Documented SSL :doc:`configuration <conf_ref>` and :doc:`repository <api_repos>` options.

Added virtual provides allowing installation of DNF commands by their name in the form of
``dnf install dnf-command(name)``.

:doc:`dnf-automatic <automatic>` now by default waits random interval between 0 and 300 seconds before any network communication is performed.


Bugs fixed in 1.0.1:

* :rhbug:`1214968`
* :rhbug:`1222694`
* :rhbug:`1225246`
* :rhbug:`1213985`
* :rhbug:`1225277`
* :rhbug:`1223932`
* :rhbug:`1223614`
* :rhbug:`1203661`
* :rhbug:`1187741`

===================
1.0.0 Release Notes
===================

Improved documentation of YUM to DNF transition in :doc:`cli_vs_yum`.

:ref:`Auto remove command <autoremove_command-label>` does not remove `installonly` packages.

:ref:`Downgrade command <downgrade_command-label>` downgrades to specified package version if that is lower than currently installed one.

DNF now uses :attr:`dnf.repo.Repo.id` as a default value for :attr:`dnf.repo.Repo.name`.

Added support of repositories which use basic HTTP authentication.

API additions in 1.0.0:

:doc:`configuration <conf_ref>` options `username` and `password` (HTTP authentication)

:attr:`dnf.repo.Repo.username` and :attr:`dnf.repo.Repo.password` (HTTP authentication)

Bugs fixed in 1.0.0:

* :rhbug:`1215560`
* :rhbug:`1199648`
* :rhbug:`1208773`
* :rhbug:`1208018`
* :rhbug:`1207861`
* :rhbug:`1201445`
* :rhbug:`1210275`
* :rhbug:`1191275`
* :rhbug:`1207965`
* :rhbug:`1215289`

===================
0.6.5 Release Notes
===================

Python 3 version of DNF is now default in Fedora 23 and later.

yum-dnf package does not conflict with yum package.

`dnf erase` was deprecated in favor of `dnf remove`.

Extended documentation of handling non-existent packages and YUM to DNF transition in :doc:`cli_vs_yum`.

API additions in 0.6.5:

Newly added `pluginconfpath` option in :doc:`configuration <conf_ref>`.

Exposed `skip_if_unavailable` attribute from :doc:`api_repos`.

Documented `IOError` exception of method `fill_sack` from :class:`dnf.Base`.

Bugs fixed in 0.6.5:

* :rhbug:`1203151`
* :rhbug:`1187579`
* :rhbug:`1185977`
* :rhbug:`1195240`
* :rhbug:`1193914`
* :rhbug:`1195385`
* :rhbug:`1160806`
* :rhbug:`1186710`
* :rhbug:`1207726`
* :rhbug:`1157233`
* :rhbug:`1190671`
* :rhbug:`1191579`
* :rhbug:`1195325`
* :rhbug:`1154202`
* :rhbug:`1189083`
* :rhbug:`1193915`
* :rhbug:`1195661`
* :rhbug:`1190458`
* :rhbug:`1194685`
* :rhbug:`1160950`

===================
0.6.4 Release Notes
===================

Added example code snippets into :doc:`use_cases`.

Shows ordered groups/environments by `display_order` tag from :ref:`cli <grouplist_command-label>` and :doc:`api_comps` DNF API.

In commands the environment group is specified the same as :ref:`group <specifying_groups-label>`.

:ref:`skip_if_unavailable <skip_if_unavailable-label>` configuration option affects the metadata only.

added `enablegroups`, `minrate` and `timeout` :doc:`configuration options <conf_ref>`

API additions in 0.6.4:

Documented `install_set` and `remove_set attributes` from :doc:`api_transaction`.

Exposed `downloadsize`, `files`, `installsize` attributes from :doc:`api_package`.

Bugs fixed in 0.6.4:

* :rhbug:`1155877`
* :rhbug:`1175466`
* :rhbug:`1175466`
* :rhbug:`1186461`
* :rhbug:`1170156`
* :rhbug:`1184943`
* :rhbug:`1177002`
* :rhbug:`1169165`
* :rhbug:`1167982`
* :rhbug:`1157233`
* :rhbug:`1138096`
* :rhbug:`1181189`
* :rhbug:`1181397`
* :rhbug:`1175434`
* :rhbug:`1162887`
* :rhbug:`1156084`
* :rhbug:`1175098`
* :rhbug:`1174136`
* :rhbug:`1055910`
* :rhbug:`1155918`
* :rhbug:`1119030`
* :rhbug:`1177394`
* :rhbug:`1154476`

===================
0.6.3 Release Notes
===================

:ref:`Deltarpm <deltarpm-label>` configuration option is set on by default.

API additions in 0.6.3:

* dnf-automatic adds :ref:`motd emitter <emit_via_automatic-label>` as an alternative output

Bugs fixed in 0.6.3:

* :rhbug:`1153543`
* :rhbug:`1151231`
* :rhbug:`1163063`
* :rhbug:`1151854`
* :rhbug:`1151740`
* :rhbug:`1110780`
* :rhbug:`1149972`
* :rhbug:`1150474`
* :rhbug:`995537`
* :rhbug:`1149952`
* :rhbug:`1149350`
* :rhbug:`1170232`
* :rhbug:`1147523`
* :rhbug:`1148208`
* :rhbug:`1109927`

===================
0.6.2 Release Notes
===================

API additions in 0.6.2:

* Now :meth:`dnf.Base.package_install` method ignores already installed packages
* `CliError` exception from :mod:`dnf.cli` documented
* `Autoerase`, `History`, `Info`, `List`, `Provides`, `Repolist` commands do not force a sync of expired :ref:`metadata <metadata_synchronization-label>`
* `Install` command does installation only

Bugs fixed in 0.6.2:

* :rhbug:`909856`
* :rhbug:`1134893`
* :rhbug:`1138700`
* :rhbug:`1070902`
* :rhbug:`1124316`
* :rhbug:`1136584`
* :rhbug:`1135861`
* :rhbug:`1136223`
* :rhbug:`1122617`
* :rhbug:`1133830`
* :rhbug:`1121184`

===================
0.6.1 Release Notes
===================

New release adds :ref:`upgrade-type command <upgrade_type_automatic-label>` to `dnf-automatic` for choosing specific advisory type updates.

Implemented missing :ref:`history redo command <history_redo_command-label>` for repeating transactions.

Supports :ref:`gpgkey <repo_gpgkey-label>` repo config, :ref:`repo_gpgcheck <repo_gpgcheck-label>` and :ref:`gpgcheck <gpgcheck-label>` [main] and Repo configs.

Distributing new package :ref:`dnf-yum <dnf_yum_package-label>` that provides `/usr/bin/yum` as a symlink to `/usr/bin/dnf`.

API additions in 0.6.1:

* `exclude`, the third parameter of :meth:`dnf.Base.group_install` now also accepts glob patterns of package names.

Bugs fixed in 0.6.1:

* :rhbug:`1132335`
* :rhbug:`1071854`
* :rhbug:`1131969`
* :rhbug:`908764`
* :rhbug:`1130878`
* :rhbug:`1130432`
* :rhbug:`1118236`
* :rhbug:`1109915`

===================
0.6.0 Release Notes
===================

0.6.0 marks a new minor version of DNF and the first release to support advisories listing with the :ref:`udpateinfo command <updateinfo_command-label>`.

Support for the :ref:`include configuration directive <include-label>` has been added. Its functionality reflects YUM's ``includepkgs`` but it has been renamed to make it consistent with the ``exclude`` setting.

Group operations now produce a list of proposed marking changes to group objects and the user is given a chance to accept or reject them just like with an ordinary package transaction.

Bugs fixed in 0.6.0:

* :rhbug:`850912`
* :rhbug:`1055910`
* :rhbug:`1116666`
* :rhbug:`1118272`
* :rhbug:`1127206`

===================
0.5.5 Release Notes
===================

The full proxy configuration, API extensions and several bugfixes are provided in this release.

API changes in 0.5.5:

* `cachedir`, the second parameter of :meth:`dnf.repo.Repo.__init__` is not optional (the method has always been this way but the documentation was not matching)

API additions in 0.5.5:

* extended description and an example provided for :meth:`dnf.Base.fill_sack`
* :attr:`dnf.conf.Conf.proxy`
* :attr:`dnf.conf.Conf.proxy_username`
* :attr:`dnf.conf.Conf.proxy_password`
* :attr:`dnf.repo.Repo.proxy`
* :attr:`dnf.repo.Repo.proxy_username`
* :attr:`dnf.repo.Repo.proxy_password`

Bugs fixed in 0.5.5:

* :rhbug:`1100946`
* :rhbug:`1117789`
* :rhbug:`1120583`
* :rhbug:`1121280`
* :rhbug:`1122900`
* :rhbug:`1123688`

===================
0.5.4 Release Notes
===================

Several encodings bugs were fixed in this release, along with some packaging issues and updates to :doc:`conf_ref`.

Repository :ref:`priority <repo_priority-label>` configuration setting has been added, providing similar functionality to YUM Utils' Priorities plugin.

Bugs fixed in 0.5.4:

* :rhbug:`1048973`
* :rhbug:`1108908`
* :rhbug:`1116544`
* :rhbug:`1116839`
* :rhbug:`1116845`
* :rhbug:`1117102`
* :rhbug:`1117293`
* :rhbug:`1117678`
* :rhbug:`1118178`
* :rhbug:`1118796`
* :rhbug:`1119032`

===================
0.5.3 Release Notes
===================

A set of bugfixes related to i18n and Unicode handling. There is a ``-4/-6`` switch and a corresponding :ref:`ip_resolve <ip-resolve-label>` configuration option (both known from YUM) to force DNS resolving of hosts to IPv4 or IPv6 addresses.

0.5.3 comes with several extensions and clarifications in the API: notably :class:`~.dnf.transaction.Transaction` is introspectible now, :class:`Query.filter <dnf.query.Query.filter>` is more useful with new types of arguments and we've hopefully shed more light on how a client is expected to setup the configuration :attr:`~dnf.conf.Conf.substitutions`.

Finally, plugin authors can now use a new :meth:`~dnf.Plugin.resolved` hook.

API changes in 0.5.3:

* extended description given for :meth:`dnf.Base.fill_sack`
* :meth:`dnf.Base.select_group` has been dropped as announced in `0.4.18 Release Notes`_

API additions in 0.5.3:

* :attr:`dnf.conf.Conf.substitutions`
* :attr:`dnf.package.Package.arch`
* :attr:`dnf.package.Package.buildtime`
* :attr:`dnf.package.Package.epoch`
* :attr:`dnf.package.Package.installtime`
* :attr:`dnf.package.Package.name`
* :attr:`dnf.package.Package.release`
* :attr:`dnf.package.Package.sourcerpm`
* :attr:`dnf.package.Package.version`
* :meth:`dnf.Plugin.resolved`
* :meth:`dnf.query.Query.filter` accepts suffixes for its argument keys now which change the filter semantics.
* :mod:`dnf.rpm`
* :class:`dnf.transaction.TransactionItem`
* :class:`dnf.transaction.Transaction` is iterable now.

Bugs fixed in 0.5.3:

* :rhbug:`1047049`
* :rhbug:`1067156`
* :rhbug:`1093420`
* :rhbug:`1104757`
* :rhbug:`1105009`
* :rhbug:`1110800`
* :rhbug:`1111569`
* :rhbug:`1111997`
* :rhbug:`1112669`
* :rhbug:`1112704`

===================
0.5.2 Release Notes
===================

This release brings `autoremove command <https://bugzilla.redhat.com/show_bug.cgi?id=963345>`_ that removes any package that was originally installed as a dependency (e.g. had not been specified as an explicit argument to the install command) and is no longer needed.

Enforced verification of SSL connections can now be disabled with the :ref:`sslverify setting <sslverify-label>`.

We have been plagued with many crashes related to Unicode and encodings since the 0.5.0 release. These have been cleared out now.

There's more: improvement in startup time, `extended globbing semantics for input arguments <https://bugzilla.redhat.com/show_bug.cgi?id=1083679>`_ and `better search relevance sorting <https://bugzilla.redhat.com/show_bug.cgi?id=1093888>`_.

Bugs fixed in 0.5.2:

* :rhbug:`963345`
* :rhbug:`1073457`
* :rhbug:`1076045`
* :rhbug:`1083679`
* :rhbug:`1092006`
* :rhbug:`1092777`
* :rhbug:`1093888`
* :rhbug:`1094594`
* :rhbug:`1095580`
* :rhbug:`1095861`
* :rhbug:`1096506`

===================
0.5.1 Release Notes
===================

Bugfix release with several internal cleanups. One outstanding change for CLI users is that DNF is a lot less verbose now during the dependency resolving phase.

Bugs fixed in 0.5.1:

* :rhbug:`1065882`
* :rhbug:`1081753`
* :rhbug:`1089864`

===================
0.5.0 Release Notes
===================

The biggest improvement in 0.5.0 is complete support for groups `and environments <https://bugzilla.redhat.com/show_bug.cgi?id=1063666>`_, including internal database of installed groups independent of the actual packages (concept known as groups-as-objects from YUM). Upgrading groups is supported now with ``group upgrade`` too.

To force refreshing of metadata before an operation (even if the data is not expired yet), `the refresh option has been added <https://bugzilla.redhat.com/show_bug.cgi?id=1064226>`_.

Internally, the CLI went through several changes to allow for better API accessibility like `granular requesting of root permissions <https://bugzilla.redhat.com/show_bug.cgi?id=1062889>`_.

API has got many more extensions, focusing on better manipulation with comps and packages. There are new entries in :doc:`cli_vs_yum` and :doc:`user_faq` too.

Several resource leaks (file descriptors, noncollectable Python objects) were found and fixed.

API changes in 0.5.0:

* it is now recommended that either :meth:`dnf.Base.close` is used, or that :class:`dnf.Base` instances are treated as a context manager.

API extensions in 0.5.0:

* :meth:`dnf.Base.add_remote_rpms`
* :meth:`dnf.Base.close`
* :meth:`dnf.Base.group_upgrade`
* :meth:`dnf.Base.resolve` optionally accepts `allow_erasing` arguments now.
* :meth:`dnf.Base.package_downgrade`
* :meth:`dnf.Base.package_install`
* :meth:`dnf.Base.package_upgrade`
* :class:`dnf.cli.demand.DemandSheet`
* :attr:`dnf.cli.Command.base`
* :attr:`dnf.cli.Command.cli`
* :attr:`dnf.cli.Command.summary`
* :attr:`dnf.cli.Command.usage`
* :meth:`dnf.cli.Command.configure`
* :attr:`dnf.cli.Cli.demands`
* :class:`dnf.comps.Package`
* :meth:`dnf.comps.Group.packages_iter`
* :data:`dnf.comps.MANDATORY` etc.

Bugs fixed in 0.5.0:

* :rhbug:`1029022`
* :rhbug:`1051869`
* :rhbug:`1061780`
* :rhbug:`1062884`
* :rhbug:`1062889`
* :rhbug:`1063666`
* :rhbug:`1064211`
* :rhbug:`1064226`
* :rhbug:`1073859`
* :rhbug:`1076884`
* :rhbug:`1079519`
* :rhbug:`1079932`
* :rhbug:`1080331`
* :rhbug:`1080489`
* :rhbug:`1082230`
* :rhbug:`1083432`
* :rhbug:`1083767`
* :rhbug:`1084139`
* :rhbug:`1084553`
* :rhbug:`1088166`

====================
0.4.19 Release Notes
====================

Arriving one week after 0.4.18, the 0.4.19 mainly provides a fix to a traceback in group operations under non-root users.

DNF starts to ship separate translation files (.mo) starting with this release.

Bugs fixed in 0.4.19:

* :rhbug:`1077173`
* :rhbug:`1078832`
* :rhbug:`1079621`

====================
0.4.18 Release Notes
====================

Support for ``dnf distro-sync <spec>`` finally arrives in this version.

DNF has moved to handling groups as objects,  tagged installed/uninstalled independently from the actual installed packages. This has been in YUM as the ``group_command=objects`` setting and the default in recent Fedora releases. There are API extensions related to this change as well as two new CLI commands: ``group mark install`` and ``group mark remove``.

API items deprecated in 0.4.8 and 0.4.9 have been dropped in 0.4.18, in accordance with our deprecation policy.

API changes in 0.4.18:

* :mod:`dnf.queries` has been dropped as announced in `0.4.8 Release Notes`_
* :exc:`dnf.exceptions.PackageNotFoundError` has been dropped from API as announced in `0.4.9 Release Notes`_
* :meth:`dnf.Base.install` no longer has to return the number of marked packages as announced in `0.4.9 Release Notes`_

API deprecations in 0.4.18:

* :meth:`dnf.Base.select_group` is deprecated now. Please use :meth:`~.Base.group_install` instead.

API additions in 0.4.18:

* :meth:`dnf.Base.group_install`
* :meth:`dnf.Base.group_remove`

Bugs fixed in 0.4.18:

* :rhbug:`963710`
* :rhbug:`1067136`
* :rhbug:`1071212`
* :rhbug:`1071501`

====================
0.4.17 Release Notes
====================

This release fixes many bugs in the downloads/DRPM CLI area. A bug got fixed preventing a regular user from running read-only operations using ``--cacheonly``. Another fix ensures that ``metadata_expire=never`` setting is respected. Lastly, the release provides three requested API calls in the repo management area.

API additions in 0.4.17:

* :meth:`dnf.repodict.RepoDict.all`
* :meth:`dnf.repodict.RepoDict.get_matching`
* :meth:`dnf.repo.Repo.set_progress_bar`

Bugs fixed in 0.4.17:

* :rhbug:`1059704`
* :rhbug:`1058224`
* :rhbug:`1069538`
* :rhbug:`1070598`
* :rhbug:`1070710`
* :rhbug:`1071323`
* :rhbug:`1071455`
* :rhbug:`1071501`
* :rhbug:`1071518`
* :rhbug:`1071677`

====================
0.4.16 Release Notes
====================

The refactorings from 0.4.15 are introducing breakage causing the background ``dnf makecache`` runs traceback. This release fixes that.

Bugs fixed in 0.4.16:

* :rhbug:`1069996`

====================
0.4.15 Release Notes
====================

Massive refactoring of the downloads handling to provide better API for reporting download progress and fixed bugs are the main things brought in 0.4.15.

API additions in 0.4.15:

* :exc:`dnf.exceptions.DownloadError`
* :meth:`dnf.Base.download_packages` now takes the optional `progress` parameter and can raise :exc:`.DownloadError`.
* :class:`dnf.callback.Payload`
* :class:`dnf.callback.DownloadProgress`
* :meth:`dnf.query.Query.filter` now also recognizes ``provides`` as a filter name.

Bugs fixed in 0.4.15:

* :rhbug:`1048788`
* :rhbug:`1065728`
* :rhbug:`1065879`
* :rhbug:`1065959`
* :rhbug:`1066743`

====================
0.4.14 Release Notes
====================

This quickly follows 0.4.13 to address the issue of crashes when DNF output is piped into another program.

API additions in 0.4.14:

* :attr:`.Repo.pkgdir`

Bugs fixed in 0.4.14:

* :rhbug:`1062390`
* :rhbug:`1062847`
* :rhbug:`1063022`
* :rhbug:`1064148`

====================
0.4.13 Release Notes
====================

0.4.13 finally ships support for `delta RPMS <https://gitorious.org/deltarpm>`_. Enabling this can save some bandwidth (and use some CPU time) when downloading packages for updates.

Support for bash completion is also included in this version. It is recommended to use the ``generate_completion_cache`` plugin to have the completion work fast. This plugin will be also shipped with ``dnf-plugins-core-0.0.3``.

The :ref:`keepcache <keepcache-label>` config option has been readded.

Bugs fixed in 0.4.13:

* :rhbug:`909468`
* :rhbug:`1030440`
* :rhbug:`1046244`
* :rhbug:`1055051`
* :rhbug:`1056400`

====================
0.4.12 Release Notes
====================

This release disables fastestmirror by default as we received many complains about it. There are also several bugfixes, most importantly an issue has been fixed that caused packages installed by Anaconda be removed together with a depending package. It is now possible to use ``bandwidth`` and ``throttle`` config values too.

Bugs fixed in 0.4.12:

* :rhbug:`1045737`
* :rhbug:`1048468`
* :rhbug:`1048488`
* :rhbug:`1049025`
* :rhbug:`1051554`

====================
0.4.11 Release Notes
====================

This is mostly a bugfix release following quickly after 0.4.10, with many updates to documentation.

API additions in 0.4.11:

* :meth:`.Plugin.read_config`
* :class:`.repo.Metadata`
* :attr:`.repo.Repo.metadata`

API changes in 0.4.11:

* :attr:`.Conf.pluginpath` is no longer hard coded but depends on the major Python version.

Bugs fixed in 0.4.11:

* :rhbug:`1048402`
* :rhbug:`1048572`
* :rhbug:`1048716`
* :rhbug:`1048719`
* :rhbug:`1048988`

====================
0.4.10 Release Notes
====================

0.4.10 is a bugfix release that also adds some long-requested CLI features and extends the plugin support with two new plugin hooks. An important feature for plugin developers is going to be the possibility to register plugin's own CLI command, available from this version.

``dnf history`` now recognizes ``last`` as a special argument, just like other history commands.

``dnf install`` now accepts group specifications via the ``@`` character.

Support for the ``--setopt`` option has been readded from YUM.

API additions in 0.4.10:

* :doc:`api_cli`
* :attr:`.Plugin.name`
* :meth:`.Plugin.__init__` now specifies the second parameter as an instance of `.cli.Cli`
* :meth:`.Plugin.sack`
* :meth:`.Plugin.transaction`
* :func:`.repo.repo_id_invalid`

API changes in 0.4.10:

* Plugin authors must specify :attr:`.Plugin.name` when authoring a plugin.

Bugs fixed in 0.4.10:

* :rhbug:`967264`
* :rhbug:`1018284`
* :rhbug:`1035164`
* :rhbug:`1036147`
* :rhbug:`1036211`
* :rhbug:`1038403`
* :rhbug:`1038937`
* :rhbug:`1040255`
* :rhbug:`1044502`
* :rhbug:`1044981`
* :rhbug:`1044999`

===================
0.4.9 Release Notes
===================

Several YUM features are revived in this release. ``dnf history rollback`` now works again. The ``history userinstalled`` has been added, it displays a list of packages that the user manually selected for installation on an installed system and does not include those packages that got installed as dependencies.

We're happy to announce that the API in 0.4.9 has been extended to finally support plugins. There is a limited set of plugin hooks now, we will carefully add new ones in the following releases. New marking operations have ben added to the API and also some configuration options.

An alternative to ``yum shell`` is provided now for its most common use case: replacing a non-leaf package with a conflicting package is achieved by using the ``--allowerasing`` switch now.

API additions in 0.4.9:

* :doc:`api_plugins`
* :ref:`logging_label`
* :meth:`.Base.read_all_repos`
* :meth:`.Base.reset`
* :meth:`.Base.downgrade`
* :meth:`.Base.remove`
* :meth:`.Base.upgrade`
* :meth:`.Base.upgrade_all`
* :attr:`.Conf.pluginpath`
* :attr:`.Conf.reposdir`

API deprecations in 0.4.9:

* :exc:`.PackageNotFoundError` is deprecated for public use. Please catch :exc:`.MarkingError` instead.
* It is deprecated to use :meth:`.Base.install` return value for anything. The method either returns or raises an exception.

Bugs fixed in 0.4.9:

* :rhbug:`884615`
* :rhbug:`963137`
* :rhbug:`991038`
* :rhbug:`1032455`
* :rhbug:`1034607`
* :rhbug:`1036116`

===================
0.4.8 Release Notes
===================

There are mainly internal changes, new API functions and bugfixes in this release.

Python 3 is fully supported now, the Fedora builds include the Py3 variant. The DNF program still runs under Python 2.7 but the extension authors can now choose what Python they prefer to use.

This is the first version of DNF that deprecates some of its API. Clients using deprecated code will see a message emitted to stderr using the standard `Python warnings module <http://docs.python.org/3.3/library/warnings.html>`_. You can filter out :exc:`dnf.exceptions.DeprecationWarning` to suppress them.

API additions in 0.4.8:

* :attr:`dnf.Base.sack`
* :attr:`dnf.conf.Conf.cachedir`
* :attr:`dnf.conf.Conf.config_file_path`
* :attr:`dnf.conf.Conf.persistdir`
* :meth:`dnf.conf.Conf.read`
* :class:`dnf.package.Package`
* :class:`dnf.query.Query`
* :class:`dnf.subject.Subject`
* :meth:`dnf.repo.Repo.__init__`
* :class:`dnf.sack.Sack`
* :class:`dnf.selector.Selector`
* :class:`dnf.transaction.Transaction`

API deprecations in 0.4.8:

* :mod:`dnf.queries` is deprecated now. If you need to create instances of :class:`.Subject`, import it from :mod:`dnf.subject`. To create :class:`.Query` instances it is recommended to use :meth:`sack.query() <dnf.sack.Sack.query>`.

Bugs fixed in 0.4.8:

* :rhbug:`1014563`
* :rhbug:`1029948`
* :rhbug:`1030998`
* :rhbug:`1030297`
* :rhbug:`1030980`

===================
0.4.7 Release Notes
===================

We start to publish the :doc:`api` with this release. It is largely
incomprehensive at the moment, yet outlines the shape of the documentation and
the process the project is going to use to maintain it.

The :ref:upgrade_requirements_on_install <upgrade_requirements_on_install_dropped> configuration option was dropped.

Bugs fixed in 0.4.7:

* :rhbug:`1019170`
* :rhbug:`1024776`
* :rhbug:`1025650`

===================
0.4.6 Release Notes
===================

0.4.6 brings two new major features. Firstly, it is the revival of ``history
undo``, so transactions can be reverted now.  Secondly, DNF will now limit the
number of installed kernels and *installonly* packages in general to the number
specified by :ref:`installonly_limit <installonly-limit-label>` configuration
option.

DNF now supports the ``group summary`` command and one-word group commands no
longer cause tracebacks, e.g. ``dnf grouplist``.

There are vast internal changes to ``dnf.cli``, the subpackage that provides CLI
to DNF. In particular, it is now better separated from the core.

The hawkey library used against DNF from with this versions uses a `recent RPMDB
loading optimization in libsolv
<https://github.com/openSUSE/libsolv/commit/843dc7e1>`_ that shortens DNF
startup by seconds when the cached RPMDB is invalid.

We have also added further fixes to support Python 3 and enabled `librepo's
fastestmirror caching optimization
<https://github.com/Tojaj/librepo/commit/b8a063763ccd8a84b8ec21a643461eaace9b9c08>`_
to tighten the download times even more.

Bugs fixed in 0.4.6:

* :rhbug:`878348`
* :rhbug:`880524`
* :rhbug:`1019957`
* :rhbug:`1020101`
* :rhbug:`1020934`
* :rhbug:`1023486`

===================
0.4.5 Release Notes
===================

A serious bug causing `tracebacks during package downloads
<https://bugzilla.redhat.com/show_bug.cgi?id=1021087>`_ made it into 0.4.4 and
this release contains a fix for that. Also, a basic proxy support has been
readded now.

Bugs fixed in 0.4.5:

* :rhbug:`1021087`

===================
0.4.4 Release Notes
===================

The initial support for Python 3 in DNF has been merged in this version. In
practice one can not yet run the ``dnf`` command in Py3 but the unit tests
already pass there. We expect to give Py3 and DNF heavy testing during the
Fedora 21 development cycle and eventually switch to it as the default. The plan
is to drop Python 2 support as soon as Anaconda is running in Python 3.

Minor adjustments to allow Anaconda support also happened during the last week,
as well as a fix to a possibly severe bug that one is however not really likely
to see with non-devel Fedora repos:

* :rhbug:`1017278`

===================
0.4.3 Release Notes
===================

This is an early release to get the latest DNF out with the latest librepo
fixing the `Too many open files
<https://bugzilla.redhat.com/show_bug.cgi?id=1015957>`_ bug.

In Fedora, the spec file has been updated to no longer depend on precise
versions of the libraries so in the future they can be released
independently.

This release sees the finished refactoring in error handling during basic
operations and adds support for ``group remove`` and ``group info`` commands,
i.e. the following two bugs:

* :rhbug:`1013764`
* :rhbug:`1013773`

===================
0.4.2 Release Notes
===================

DNF now downloads packages for the transaction in parallel with progress bars
updated to effectively represent this. Since so many things in the downloading
code were changing, we figured it was a good idea to finally drop urlgrabber
dependency at the same time. Indeed, this is the first version that doesn't
require urlgrabber for neither build nor run.

Similarly, since `librepo started to support this
<https://github.com/Tojaj/librepo/commit/acf458f29f7234d2d8d93a68391334343beae4b9>`_,
downloads in DNF now use the fastest mirrors available by default.

The option to :ref:`specify repositories' costs <repo_cost-label>` has been
readded.

Internally, DNF has seen first part of ongoing refactorings of the basic
operations (install, update) as well as a couple of new API methods supporting
development of extensions.

These bugzillas are fixed in 0.4.2:

* :rhbug:`909744`
* :rhbug:`984529`
* :rhbug:`967798`
* :rhbug:`995459`

===================
0.4.1 Release Notes
===================

The focus of this release was to support our efforts in implementing the DNF
Payload for Anaconda, with changes on the API side of things (better logging,
new ``Base.reset()`` method).

Support for some irrelevant config options has been dropped (``kernelpkgnames``,
``exactarch``, ``rpm_check_debug``). We also no longer detect metalinks in the
``mirrorlist`` option (see `Fedora bug 948788
<https://bugzilla.redhat.com/show_bug.cgi?id=948788>`_).

DNF is on its way to drop the urlgrabber dependency and the first set of patches
towards this goal is already in.

Expect the following bugs to go away with upgrade to 0.4.1:

* :rhbug:`998859`
* :rhbug:`1006366`
* :rhbug:`1008444`
* :rhbug:`1003220`

===================
0.4.0 Release Notes
===================

The new minor version brings many internal changes to the comps code, most comps
parsing and processing is now delegated to `libcomps
<https://github.com/midnightercz/libcomps>`_ by Jindřich Luža.

The ``overwrite_groups`` config option has been dropped in this version and DNF
acts if it was 0, that is groups with the same name are merged together.

The currently supported groups commands (``group list`` and ``group install``)
are documented on the manpage now.

The 0.4.0 version is the first one supported by the DNF Payload for Anaconda and
many changes since 0.3.11 make that possible by cleaning up the API and making
it more sane (cleanup of ``yumvars`` initialization API, unifying the RPM
transaction callback objects hierarchy, slimming down ``dnf.rpmUtils.arch``,
improved logging).

Fixes for the following are contained in this version:

* :rhbug:`997403`
* :rhbug:`1002508`
* :rhbug:`1002798`

====================
0.3.11 Release Notes
====================

The default multilib policy configuration value is ``best`` now. This does not
pose any change for the Fedora users because exactly the same default had been
previously achieved by a setting in ``/etc/dnf/dnf.conf`` shipped with the
Fedora package.

An important fix to the repo module speeds up package downloads again is present
in this release. The full list of fixes is:

* :rhbug:`979042`
* :rhbug:`977753`
* :rhbug:`996138`
* :rhbug:`993916`

====================
0.3.10 Release Notes
====================

The only major change is that ``skip_if_unavailable`` is :ref:`enabled by
default now <skip_if_unavailable_default>`.

A minor release otherwise, mainly to get a new version of DNF out that uses a
fresh librepo. The following issues are now a thing of the past:

* :rhbug:`977661`
* :rhbug:`984483`
* :rhbug:`986545`

===================
0.3.9 Release Notes
===================

This is a quick bugfix release dealing with reported bugs and tracebacks:

* :rhbug:`964584`
* :rhbug:`979942`
* :rhbug:`980227`
* :rhbug:`981310`

===================
0.3.8 Release Notes
===================

A new locking module has been integrated in this version, clients should see the
message about DNF lock being taken less often.

Panu Matilainen has submitted many patches to this release to cleanup the RPM
interfacing modules.

The following bugs are fixed in this release:

* :rhbug:`908491`
* :rhbug:`968159`
* :rhbug:`974427`
* :rhbug:`974866`
* :rhbug:`976652`
* :rhbug:`975858`

===================
0.3.7 Release Notes
===================

This is a bugfix release:

* :rhbug:`916662`
* :rhbug:`967732`

===================
0.3.6 Release Notes
===================

This is a bugfix release, including the following fixes:

* :rhbug:`966372`
* :rhbug:`965410`
* :rhbug:`963627`
* :rhbug:`965114`
* :rhbug:`964467`
* :rhbug:`963680`
* :rhbug:`963133`

===================
0.3.5 Release Notes
===================

Besides few fixed bugs this version should not present any differences for the
user. On the inside, the transaction managing mechanisms have changed
drastically, bringing code simplification, better maintainability and better
testability.

In Fedora, there is a change in the spec file effectively preventing the
makecache timer from running *immediately after installation*. The timer
service is still enabled by default, but unless the user starts it manually with
``systemctl start dnf-makecache.timer`` it will not run until after the first
reboot. This is in alignment with Fedora packaging best practices.

The following bugfixes are included in 0.3.5:

* :rhbug:`958452`
* :rhbug:`959990`
* :rhbug:`961549`
* :rhbug:`962188`

===================
0.3.4 Release Notes
===================

0.3.4 is the first DNF version since the fork from YUM that is able to
manipulate the comps data. In practice, ``dnf group install <group name>`` works
again. No other group commands are supported yet.

Support for ``librepo-0.0.4`` and related cleanups and extensions this new
version allows are included (see the buglist below)

This version has also improved reporting of obsoleted packages in the CLI (the
YUM-style "replacing <package-nevra>" appears in the textual transaction
overview).

The following bugfixes are included in 0.3.4:

* :rhbug:`887317`
* :rhbug:`914919`
* :rhbug:`922667`

===================
0.3.3 Release Notes
===================

The improvements in 0.3.3 are only API changes to the logging. There is a new
module ``dnf.logging`` that defines simplified logging structure compared to
YUM, with fewer logging levels and `simpler usage for the developers
<https://github.com/rpm-software-management/dnf/wiki/Hacking#logging>`_. The RPM transaction logs are
no longer in ``/var/log/dnf.transaction.log`` but in ``/var/log/dnf.rpm.log`` by
default.

The exception classes were simplified and moved to ``dnf.exceptions``.

The following bugs are fixed in 0.3.3:

* :rhbug:`950722`
* :rhbug:`903775`

===================
0.3.2 Release Notes
===================

The major improvement in this version is in speeding up syncing of repositories
using metalink by looking at the repomd.xml checksums. This effectively lets DNF
cheaply refresh expired repositories in cases where the original has not
changed\: for instance the main Fedora repository is refreshed with one 30 kB
HTTP download. This functionality is present in the current YUM but hasn't
worked in DNF since 3.0.0.

Otherwise this is mainly a release fixing bugs and tracebacks. The following
reported bugs are fixed:

* :rhbug:`947258`
* :rhbug:`889202`
* :rhbug:`923384`

===================
0.3.1 Release Notes
===================

0.3.1 brings mainly changes to the automatic metadata synchronization. In
Fedora, ``dnf makecache`` is triggered via SystemD timers now and takes an
optional ``background`` extra-argument to run in resource-considerate mode (no
syncing when running on laptop battery, only actually performing the check at
most once every three hours). Also, the IO and CPU priorities of the
timer-triggered process are lowered now and shouldn't as noticeably impact the
system's performance.

The administrator can also easily disable the automatic metadata updates by
setting :ref:`metadata_timer_sync <metadata_timer_sync-label>` to 0.

The default value of :ref:`metadata_expire <metadata_expire-label>` was
increased from 6 hours to 48 hours. In Fedora, the repos usually set this
explicitly so this change is not going to cause much impact.

The following reported issues are fixed in this release:

* :rhbug:`916657`
* :rhbug:`921294`
* :rhbug:`922521`
* :rhbug:`926871`
* :rhbug:`878826`
* :rhbug:`922664`
* :rhbug:`892064`
* :rhbug:`919769`
