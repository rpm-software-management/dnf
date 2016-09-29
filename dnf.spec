%global hawkey_version 0.7.0
%global librepo_version 1.7.19
%global libcomps_version 0.1.8
%global rpm_version 4.13.0-0.rc1.29
%global min_plugins_core 0.1.13
%global dnf_langpacks_ver 0.15.1-6

%global confdir %{_sysconfdir}/%{name}

%global pluginconfpath %{confdir}/plugins
%global py2pluginpath %{python2_sitelib}/%{name}-plugins

%if 0%{?rhel} && 0%{?rhel} <= 7
%bcond_with python3
%else
%bcond_without python3
%endif

%if %{with python3}
%global py3pluginpath %{python3_sitelib}/%{name}-plugins
%endif

# Use the same directory of the main package for subpackage licence and docs
%global _docdir_fmt %{name}

Name:           dnf
Version:        2.0.0
Release:        0.rc1.1%{?dist}
Summary:        Package manager forked from Yum, using libsolv as a dependency resolver
# For a breakdown of the licensing, see PACKAGE-LICENSING
License:        GPLv2+ and GPLv2 and GPL
URL:            https://github.com/rpm-software-management/dnf
Source0:        %{url}/archive/%{name}-%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  cmake
BuildRequires:  gettext
BuildRequires:  python-bugzilla
BuildRequires:  python-sphinx
BuildRequires:  systemd
BuildRequires:  bash-completion
%if %{with python3}
Requires:       python3-%{name} = %{version}-%{release}
%else
Requires:       python2-%{name} = %{version}-%{release}
%endif
Requires(post):     systemd
Requires(preun):    systemd
Requires(postun):   systemd
Provides:       dnf-command(autoremove)
Provides:       dnf-command(check-update)
Provides:       dnf-command(clean)
Provides:       dnf-command(distro-sync)
Provides:       dnf-command(downgrade)
Provides:       dnf-command(group)
Provides:       dnf-command(history)
Provides:       dnf-command(info)
Provides:       dnf-command(install)
Provides:       dnf-command(list)
Provides:       dnf-command(makecache)
Provides:       dnf-command(mark)
Provides:       dnf-command(provides)
Provides:       dnf-command(reinstall)
Provides:       dnf-command(remove)
Provides:       dnf-command(repolist)
Provides:       dnf-command(repoquery)
Provides:       dnf-command(repository-packages)
Provides:       dnf-command(search)
Provides:       dnf-command(updateinfo)
Provides:       dnf-command(upgrade)
Provides:       dnf-command(upgrade-to)
Conflicts:      python2-dnf-plugins-core < %{min_plugins_core}
Conflicts:      python3-dnf-plugins-core < %{min_plugins_core}

# dnf-langpacks package is retired in F25
# to have clean upgrade path for dnf-langpacks
Obsoletes:      dnf-langpacks < %{dnf_langpacks_ver}

%description
Package manager forked from Yum, using libsolv as a dependency resolver.

%package conf
Summary:        Configuration files for DNF
Requires:       libreport-filesystem
# dnf-langpacks package is retired in F25
# to have clean upgrade path for dnf-langpacks
Obsoletes:      dnf-langpacks-conf < %{dnf_langpacks_ver}

%description conf
Configuration files for DNF.

%package yum
Conflicts:      yum < 3.4.3-505
Requires:       %{name} = %{version}-%{release}
Summary:        As a Yum CLI compatibility layer, supplies /usr/bin/yum redirecting to DNF

%description yum
As a Yum CLI compatibility layer, supplies /usr/bin/yum redirecting to DNF.

%package -n python2-%{name}
Summary:        Python 2 interface to DNF
%{?python_provide:%python_provide python2-%{name}}
BuildRequires:  python2-devel
BuildRequires:  python-hawkey >= %{hawkey_version}
BuildRequires:  python-iniparse
BuildRequires:  python-libcomps >= %{libcomps_version}
BuildRequires:  python-librepo >= %{librepo_version}
BuildRequires:  python-nose
%if 0%{?rhel} && 0%{?rhel} <= 7
BuildRequires:  pygpgme
%else
BuildRequires:  python2-pygpgme
%endif
BuildRequires:  pyliblzma
BuildRequires:  rpm-python >= %{rpm_version}
Recommends:     bash-completion
Requires:       pyliblzma
Requires:       %{name}-conf = %{version}-%{release}
Requires:       deltarpm
Requires:       python-hawkey >= %{hawkey_version}
Requires:       python-iniparse
Requires:       python-libcomps >= %{libcomps_version}
Requires:       python-librepo >= %{librepo_version}
%if 0%{?rhel} && 0%{?rhel} <= 7
Requires:       pygpgme
%else
Requires:       python2-pygpgme
%endif
Requires:       rpm-plugin-systemd-inhibit
Requires:       rpm-python >= %{rpm_version}
# dnf-langpacks package is retired in F25
# to have clean upgrade path for dnf-langpacks
Obsoletes:      python-dnf-langpacks < %{dnf_langpacks_ver}

%description -n python2-%{name}
Python 2 interface to DNF.

%if %{with python3}
%package -n python3-%{name}
Summary:        Python 3 interface to DNF.
%{?system_python_abi}
%{?python_provide:%python_provide python3-%{name}}
BuildRequires:  python3-devel
BuildRequires:  python3-hawkey >= %{hawkey_version}
BuildRequires:  python3-iniparse
BuildRequires:  python3-libcomps >= %{libcomps_version}
BuildRequires:  python3-librepo >= %{librepo_version}
BuildRequires:  python3-nose
BuildRequires:  python3-pygpgme
BuildRequires:  rpm-python3 >= %{rpm_version}
Recommends:     bash-completion
Requires:       %{name}-conf = %{version}-%{release}
Requires:       deltarpm
Requires:       python3-hawkey >= %{hawkey_version}
Requires:       python3-iniparse
Requires:       python3-libcomps >= %{libcomps_version}
Requires:       python3-librepo >= %{librepo_version}
Requires:       python3-pygpgme
Requires:       rpm-plugin-systemd-inhibit
Requires:       rpm-python3 >= %{rpm_version}
# dnf-langpacks package is retired in F25
# to have clean upgrade path for dnf-langpacks
Obsoletes:      python3-dnf-langpacks < %{dnf_langpacks_ver}

%description -n python3-%{name}
Python 3 interface to DNF.
%endif

%package automatic
Summary:        Alternative CLI to "dnf upgrade" suitable for automatic, regular execution.
BuildRequires:  systemd
Requires:       %{name} = %{version}-%{release}
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description automatic
Alternative CLI to "dnf upgrade" suitable for automatic, regular execution.

%prep
%autosetup
mkdir build
%if %{with python3}
mkdir build-py3
%endif

%build
pushd build
  %cmake ..
  %make_build
  make doc-man
popd
%if %{with python3}
pushd build-py3
  %cmake .. -DPYTHON_DESIRED:str=3 -DWITH_MAN=0
  %make_build
popd
%endif

%install
pushd build
  %make_install
popd
%if %{with python3}
pushd build-py3
  %make_install
popd
%endif
%find_lang %{name}

mkdir -p %{buildroot}%{pluginconfpath}/
mkdir -p %{buildroot}%{py2pluginpath}/
%if %{with python3}
mkdir -p %{buildroot}%{py3pluginpath}/__pycache__/
%endif
mkdir -p %{buildroot}%{_localstatedir}/log/
mkdir -p %{buildroot}%{_var}/cache/dnf/
touch %{buildroot}%{_localstatedir}/log/%{name}.log
%if %{with python3}
%{?system_python_abi:sed -i 's|#!%{__python3}|#!%{_libexecdir}/system-python|' %{buildroot}%{_bindir}/dnf-3}
ln -sr %{buildroot}%{_bindir}/dnf-3 %{buildroot}%{_bindir}/dnf
mv %{buildroot}%{_bindir}/dnf-automatic-3 %{buildroot}%{_bindir}/dnf-automatic
%else
ln -sr %{buildroot}%{_bindir}/dnf-2 %{buildroot}%{_bindir}/dnf
mv %{buildroot}%{_bindir}/dnf-automatic-2 %{buildroot}%{_bindir}/dnf-automatic
%endif
rm -vf %{buildroot}%{_bindir}/dnf-automatic-*

%check
pushd build
  ctest -VV
popd
%if %{with python3}
pushd build-py3
  ctest -VV
popd
%endif

%post
%systemd_post dnf-makecache.timer

%preun
%systemd_preun dnf-makecache.timer

%postun
%systemd_postun_with_restart dnf-makecache.timer

%post automatic
%systemd_post dnf-automatic.timer

%preun automatic
%systemd_preun dnf-automatic.timer

%postun automatic
%systemd_postun_with_restart dnf-automatic.timer

%files -f %{name}.lang
%{_bindir}/%{name}
%if 0%{?rhel} && 0%{?rhel} <= 7
%{_sysconfdir}/bash_completion.d/%{name}
%else
%dir %{_datadir}/bash-completion
%dir %{_datadir}/bash-completion/completions
%{_datadir}/bash-completion/completions/%{name}
%endif
%{_mandir}/man8/%{name}.8*
%{_mandir}/man8/yum2dnf.8*
%{_unitdir}/%{name}-makecache.service
%{_unitdir}/%{name}-makecache.timer
%{_var}/cache/%{name}/

%files conf
%license COPYING PACKAGE-LICENSING
%doc AUTHORS README.rst
%dir %{confdir}
%dir %{pluginconfpath}
%dir %{confdir}/protected.d
%config(noreplace) %{confdir}/%{name}.conf
%config(noreplace) %{confdir}/protected.d/%{name}.conf
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%ghost %{_localstatedir}/log/hawkey.log
%ghost %{_localstatedir}/log/%{name}.log
%ghost %{_localstatedir}/log/%{name}.librepo.log
%ghost %{_localstatedir}/log/%{name}.rpm.log
%ghost %{_localstatedir}/log/%{name}.plugin.log
%ghost %{_sharedstatedir}/%{name}
%ghost %{_sharedstatedir}/%{name}/groups.json
%ghost %{_sharedstatedir}/%{name}/yumdb
%ghost %{_sharedstatedir}/%{name}/history
%{_mandir}/man5/%{name}.conf.5.gz
%{_tmpfilesdir}/%{name}.conf
%{_sysconfdir}/libreport/events.d/collect_dnf.conf

%files yum
%{_bindir}/yum
%{_mandir}/man8/yum.8.gz

%files -n python2-%{name}
%{_bindir}/%{name}-2
%exclude %{python2_sitelib}/%{name}/automatic
%{python2_sitelib}/%{name}/
%dir %{py2pluginpath}

%if %{with python3}
%files -n python3-%{name}
%{_bindir}/%{name}-3
%exclude %{python3_sitelib}/%{name}/automatic
%{python3_sitelib}/%{name}/
%dir %{py3pluginpath}
%dir %{py3pluginpath}/__pycache__
%endif

%files automatic
%{_bindir}/%{name}-automatic
%config(noreplace) %{confdir}/automatic.conf
%{_mandir}/man8/%{name}.automatic.8.gz
%{_unitdir}/%{name}-automatic.service
%{_unitdir}/%{name}-automatic.timer
%if %{with python3}
%{python3_sitelib}/%{name}/automatic/
%else
%{python2_sitelib}/%{name}/automatic/
%endif

%changelog
* Thu Sep 29 2016 Michal Luscon <mluscon@redhat.com> 2.0.0-0.rc1.1
- See http://dnf.readthedocs.io/en/latest/release_notes.html

* Thu Sep 08 2016 Igor Gnatenko <ignatenko@redhat.com> - 1.1.10-2
- Obsolete dnf-langpacks
- Backport patch for dnf repolist disabled

* Thu Aug 18 2016 Igor Gnatenko <ignatenko@redhat.com> - 1.1.10-1
- Update to 1.1.10

* Tue Aug 09 2016 Igor Gnatenko <ignatenko@redhat.com> - 1.1.9-6
- Fix typo

* Tue Aug 09 2016 Igor Gnatenko <ignatenko@redhat.com> - 1.1.9-5
- Also change shebang for %%{?system_python_abi} in %%{_bindir}/dnf

* Tue Aug 09 2016 Igor Gnatenko <ignatenko@redhat.com> - 1.1.9-4
- Add %%{?system_python_abi}

* Tue Jul 19 2016 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1.9-3
- https://fedoraproject.org/wiki/Changes/Automatic_Provides_for_Python_RPM_Packages

* Tue May 24 2016 Michal Luscon <mluscon@redhat.com> 1.1.9-2
- Revert "group: treat mandatory pkgs as mandatory if strict=true" (RhBug:1337731)
- enforce-api: reflect changes from #992475 in completion_helper (RhBug:1338504)
- enforce-api: add compatibility methods for renamed counterparts (RhBug:1338564)

* Thu May 19 2016 Igor Gnatenko <ignatenko@redhat.com> 1.1.9-1
- doc: release notes 1.1.9 (Igor Gnatenko)
- spec: correctly set up requirements for python subpkg (Igor Gnatenko)
- spec: follow new packaging guidelines & make compatible with el7 (Igor
  Gnatenko)
- zanata update (Jan Silhan)
- enforce-api: add missing bits of Base class (Michal Luscon)
- help: unify help msg strings (Michal Luscon)
- enforce-api: decorate Base class (Michal Luscon)
- util: add decorator informing users of nonapi functions (Michal Luscon)
- Added description for 'autoremove' in dnf help (RhBug:1324086) (Abhijeet
  Kasurde)
- i18n: fixup for 0db13feed (Michal Luscon)
- i18n: use fallback mode if terminal does not support UTF-8 (RhBug:1332012)
  (Michal Luscon)
- Revert "spec: follow new packaging guidelines & make compatible with el7"
  (Michal Luscon)
- move autoglob feature directly to filterm() and filter() (Michael Mraka)
- group: treat mandatory pkgs as mandatory if strict=true (RhBug:1292892)
  (Michal Luscon)
- locks: fix lock paths in tmpfsd config since cachedir has been changed
  (Michal Luscon)
- remove formating from translation strings (Michal Luscon)
- base: set diskspace check filter before applying the filters (RhBug:1328674)
  (Michal Luscon)
- order repos by priority and cost (Michael Mraka)
- spec: follow new packaging guidelines & make compatible with el7 (Igor
  Gnatenko)
- bash-completion: first try to set fallback to BASH_COMPLETION_COMPATDIR (Igor
  Gnatenko)
- updated copyrights for files changed this year (Michael Mraka)
- cli: fix warning from re.split() about non-empty pattern (RhBug:1286556)
  (Igor Gnatenko)
- update authors file (Michal Luscon)
- Define __hash__ method for YumHistoryPackage (RhBug:1245121) (Max Prokhorov)

* Tue Apr 05 2016 Michal Luscon <mluscon@redhat.com> 1.1.8-1
- refactor: repo: add md_expired property (Michal Domonkos)
- test: fix cachedir usage in LocalRepoTest (Michal Domonkos)
- clean: operate on all cached repos (RhBug:1278225) (Michal Domonkos)
- refactor: repo: globally define valid repoid chars (Michal Domonkos)
- RepoPersistor: only write to disk when requested (Michal Domonkos)
- clean: remove dead subcommands (Michal Domonkos)
- doc: --best in case of problem (RhBug:1309408) (Jan Silhan)
- Added fix for correct error message for group info (RhBug:1209649) (Abhijeet
  Kasurde)
- repo: don't get current timeout for librepo (RhBug:1272977) (Igor Gnatenko)
- doc: fix default timeout value (Michal Luscon)
- cli: inform only about nonzero md cache check interval (Michal Luscon)
- base: report errors in batch at the end of md downloading (Michal Luscon)
- repo: produce more sane error if md download fails (Michal Luscon)
- zanata update (RhBug:1322226) (Jan Silhan)
- doc: Fixed syntax of `assumeyes` and `defaultyes` ref lables in
  `conf_ref.rst` (Matt Sturgeon)
- Fix output headers for dnf history command (Michael Dunphy)
- doc: change example of 'dnf-command(repoquery)' (Jaroslav Mracek)
- makacache.service: shorten journal logs (RhBug:1315349) (Michal Luscon)
- config: improve UX of error msg (Michal Luscon)
- Added user friendly message for out of range value (RhBug:1214562) (Abhijeet
  Kasurde)
- doc: prefer repoquery to list (Jan Silhan)
- history: fix empty history cmd (RhBug:1313215) (Michal Luscon)
- Very minor tweak to the docs for `--assumeyes` and `--assumeno` (Matt
  Sturgeon)

* Thu Feb 25 2016 Michal Luscon <mluscon@redhat.com> 1.1.7-1
- Add `/etc/distro.repos.d` as a path owned by the dnf package (Neal Gompa
  (ニール・ゴンパ))
- Change order of search and add new default repodirs (RhBug:1286477) (Neal
  Gompa (ニール・ゴンパ))
- group: don't mark available packages as installed (RhBug:1305356) (Jan
  Silhan)
- history: adjust demands for particular subcommands (RhBug:1258503) (Michal
  Luscon)
- Added extension command for group list (RhBug:1283432) (Abhijeet Kasurde)
- perf: dnf repository-packages <repo> upgrade (RhBug:1306304) (Jan Silhan)
- sack: Pass base.conf.substitutions["arch"] to sack in build_sack() function.
  (Daniel Mach)
- build: make python2/3 binaries at build time (Michal Domonkos)
- fix dnf history traceback (RhBug:1303149) (Jan Silhan)
- cli: truncate expiration msg (RhBug:1302217) (Michal Luscon)

* Mon Jan 25 2016 Michal Luscon <mluscon@redhat.com> 1.1.6-1
- history: don't fail if there is no history (RhBug:1291895) (Michal Luscon)
- Allow dnf to use a socks5 proxy, since curl support it (RhBug:1256587)
  (Michael Scherer)
- output: do not log rpm info twice (RhBug:1287221) (Michal Luscon)
- dnf owns /var/lib/dnf dir (RhBug:1294241) (Jan Silhan)
- Fix handling of repo that never expire (RhBug:1289166) (Jaroslav Mracek)
- Filter out .src packages when multilib_proto=all (Jeff Smith)
- Enable string for translation (RhBug:1294355) (Parag Nemade)
- Let logging format messages on demand (Ville Skyttä)
- clean: include metadata of local repos (RhBug:1226322) (Michal Domonkos)
- completion: Install to where bash-completion.pc says (Ville Skyttä)
- spec: bash completion is not a %%config file (Ville Skyttä)
- Change assertion handling for rpmsack.py (RhBug:1275878) (Jaroslav Mracek)
- cli: fix storing arguments in history (RhBug:1239274) (Ting-Wei Lan)

* Thu Dec 17 2015 Michal Luscon <mluscon@redhat.com> 1.1.5-1
- base: save group persistor only after successful transaction (RhBug:1229046)
  (Michal Luscon)
- base: do not clean tempfiles after remove transaction (RhBug:1282250) (Michal
  Luscon)
- base: clean packages that do not belong to any trans (Michal Luscon)
- upgrade: allow group upgrade via @ syntax (RhBug:1265391) (Michal Luscon)
- spec: Mark license files as %%license where available (Ville Skyttä)
- Remove unused imports (Ville Skyttä)
- Spelling fixes (Ville Skyttä)
- Fix typos in documentation (Rob Cutmore)
- parser: add support for braces in substitution (RhBug:1283017) (Dave
  Johansen)
- completion_helper: Don't omit "packages" from clean completions (Ville
  Skyttä)
- bash-completion: Avoid unnecessary python invocation per _dnf_helper (Ville
  Skyttä)
- repo: Download drpms early (RhBug:1260421) (Ville Skyttä)
- clean: Don't hardcode list of args in two places (Ville Skyttä)
- cli: don't crash if y/n and sys.stdin is None (RhBug:1278382) (Adam
  Williamson)
- sp err "environement" -> "environment" (Michael Goodwin)
- Remove -OO from #!/usr/bin/python (RhBug:1230820) (Jaroslav Mracek)
- cli: warn if plugins are disabled (RhBug:1280240) (Michal Luscon)

* Mon Nov 16 2015 Michal Luscon <mluscon@redhat.com> 1.1.4-1
- AUTHORS: updated (Jan Silhan)
- query: add compatibility methods (Michal Luscon)
- query: add recent, extras and autoremove methods to Query (Michal Luscon)
- query: add duplicated and latest-limit queries into api (Michal Luscon)
- format the email message with its as_string method (Olivier Andrieu)
- added dnf.i18n.ucd* functions as deprecated API (Jan Silhan)
- i18n: unicode resulting translations (RhBug:1278031) (Jan Silhan)
- po: get rid of new lines in translation (Jan Silhan)
- output: add skip count to summary (RhBug:1264032) (Michal Domonkos)
- groups: fix environment upgrade (Michal Luscon)
- Fix plural strings extraction (RhBug:1209056) (Baurzhan Muftakhidinov)
- po: fixed malformed beginning / ending (Jan Silhan)
- zanata update (Jan Silhan)
- cli: prevent tracebacks after C^ (RhBug:1274946) (Michal Luscon)

* Wed Oct 14 2015 Michal Luscon <mluscon@redhat.com> 1.1.3-1
- Update command_ref.rst (Jaroslav Mracek)
- Change in automatic.conf email settings to prevent email error with default
  sender name (Jaroslav Mracek)
- Replace assert_called() with assert_called_with() for Py35 support (Neal
  Gompa (ニール・ゴンパ))
- doc: improve documentation (Jaroslav Mracek)
- doc: update the instructions related to nightly builds (Radek Holy)
- Revert "Add the continuous integration script" (Radek Holy)
- Revert "cosmetic: ci: fix the Copr name in the README" (Radek Holy)
- Fix typo in Command.canonical's doctring (Timo Wilken)
- base: group_install is able to exclude mandatory packages
  (Related:RhBug:1199868) (Jan Silhan)

* Wed Sep 30 2015 Michal Luscon <mluscon@redhat.com> 1.1.2-4
- don't import readline as it causes crashes in Anaconda
  (related:RhBug:1258364)

* Tue Sep 22 2015 Michal Luscon <mluscon@redhat.com> 1.1.2-3
- Revert "completion_helper: don't get IndexError (RhBug:1250038)"

* Tue Sep 22 2015 Michal Luscon <mluscon@redhat.com> 1.1.2-2
- add hawkey version requirement
- revert commit #70956

* Tue Sep 22 2015 Michal Luscon <mluscon@redhat.com> 1.1.2-1
- doc: release notes 1.1.2 (Michal Luscon)
- sanitize non Unicode command attributes (RhBug:1262082) (Jan Silhan)
- don't redirect confirmation to stderr RhBug(1258364) (Vladan Kudlac)
- clean: add rpmdb to usage (Vladan Kudlac)
- completion_helper: don't get IndexError (RhBug:1250038) (Vladan Kudlac)
- add --downloadonly switch (RhBug:1048433) (Adam Salih)
- Add globbing support to base.by_provides() (RhBug:11259650) (Valentina
  Mukhamedzhanova)
- spec: packaging python(3)-dnf according to new Fedora guidelines
  (RhBug:1260198) (Jaroslav Mracek)
- Bug in Source0: URL in dnf.spec fixed (RhBug:126255) (Jaroslav Mracek)
- To dnf.spec added provides dnf-command(command name) for 21 dnf commands
  (RhBug:1259657) (jmracek)
- Expire repo cache on failed package download (Valentina Mukhamedzhanova)
- cosmetic: ci: fix the Copr name in the README (Radek Holy)
- Add the continuous integration script (Radek Holy)
- Set proper charset on email in dnf-automatic (RhBug:1254982) (Valentina
  Mukhamedzhanova)
- doc: improve configuration description (RhBug:1261766) (Michal Luscon)
- remove: show from which repo a package is (Vladan Kudlac)
- list: show from which repo a package is (RhBug:1234491) (Vladan Kudlac)
- Spelling/grammar fixes (Ville Skyttä)
- install: fix crash when terminal window is small (RhBug:1256531) (Vladan
  Kudlac)
- install: mark unification of the progress bar (Vladan Kudlac)
- fix translations in python3 (RhBug:1254687) (Michal Luscon)
- group: CompsQuery now returns group ids (RhBug:1261656) (Michal Luscon)

* Tue Sep 08 2015 Michal Luscon <mluscon@redhat.com> 1.1.1-2
- fix access to demands (RhBug:1259194) (Jan Silhan)
- make clean_requiremets_on_remove=True (RhBug:1260280) (Jan Silhan)

* Mon Aug 31 2015 Michal Luscon <mluscon@redhat.com> 1.1.1-1
- Fixed typo (RhBug:1249319) (Adam Salih)
- fixed downgrade with wildcard (RhBug:1234763) (Adam Salih)
- reorganize logic of get_best_selector(s) and query (RhBug:1242946) (Adam
  Salih)
- completion_helper: don't crash if exception occurred (RhBug:1225225) (Igor
  Gnatenko)
- base: expire cache if repo is not available (Michal Luscon)
- Don't suggest --allowerasing if it is enabled (Christian Stadelmann)
- translation works in python3 (RhBug:1254687) (Jan Silhan)
- logrotate less often (RhBug:1247766) (Jan Silhan)
- implement dnf mark command (RhBug:1125925) (Michal Luscon)
- groups: use comps data to migrate persistor (Michal Luscon)
- groups: preserve api compatibility (Michal Luscon)
- groups: use persistor data for removing env/group (Michal Luscon)
- persistor: add migration and bump version (Michal Luscon)
- persistor: store name and ui_name of group (Michal Luscon)
- show real metadata timestamp on the server in verbose mode (Jan Silhan)
- lock: make rpmdb lock blocking (RhBug:1210289) (Michal Luscon)

* Wed Aug 12 2015 Michal Luscon <mluscon@redhat.com> 1.1.0-2
- update: installonly pkgs are not shown in both install and skipped section
  (RhBug:1252415) (Jan Silhan)
- output: sort skipped packages (Jan Silhan)
- output: skipped conflicts are set (RhBug:1252032) (Jan Silhan)
- keep the dwongrading package installed if transaction fails (RhBug:1249379)
  (Jan Silhan)
- don't store empty attributes (RhBug:1246928) (Michael Mraka)
- doc: correct dnf.conf man section (RhBug:1245349) (Michal Luscon)

* Mon Aug 10 2015 Michal Luscon <mluscon@redhat.com> 1.1.0-1
- print skipped pkg with broken deps too (Related:RhBug:1210445) (Jan Silhan)
- history: set commands output as default (RhBug:1218401) (Michal Luscon)
- Update es.po. save:guardar -> save:ahorrar (Máximo Castañeda)
- cosmetic: option arg in Base.*install is replaced with strict (Jan Silhan)
- group: don't fail on first non-existing group (Jan Silhan)
- install: skips local pkgs of lower version when strict=0
  (Related:RhBug:1227952) (Jan Silhan)
- install: skip broken/conflicting packages in groups when strict=0 (Jan
  Silhan)
- install: skip broken/conflicting packages when strict=0 (Jan Silhan)
- implemented `strict` config option working in install cmd (RhBug:1197456)
  (Jan Silhan)
- fixed 'dnf --quiet repolist' lack of output (RhBug:1236310) (Nick Coghlan)
- Add support for MIPS architecture (Michal Toman)
- package: respect baseurl attribute in localPkg() (RhBug:1219638) (Michal
  Luscon)
- Download error message is not written on the same line as progress bar
  anymore (RhBug: 1224248) (Adam Salih)
- dnf downgrade does not try to downgrade not installed packages (RhBug:
  1243501) (max9631)
- pkgs not installed due to rpm error are reported (RhBug:1207981) (Adam Salih)
- dnf install checks availability of all given packages (RhBug:1208918) (Adam
  Salih)
- implemented install_weak_deps config option (RhBug:1221635) (Jan Silhan)
- ignore SIGPIPE (RhBug:1236306) (Michael Mraka)
- always add LoggingTransactionDisplay to the list of transaction displays
  (RhBug:1234639) (Radek Holy)
- Add missing FILES section (RhBug: 1225237) (Adam Salih)
- doc: Add yum vs dnf hook information (RhBug:1244486) (Parag Nemade)
- doc: clarify the expected type of the do_transactions's display parameter
  (Radek Holy)
- apichange: add dnf.cli.demand.DemandSheet.transaction_display (Radek Holy)
- apichange: add dnf.callback.TransactionProgress (Radek Holy)
- move the error output from TransactionDisplay into a separate class (Radek
  Holy)
- rename TransactionDisplay.errorlog to TransactionDisplay.error (Radek Holy)
- report package verification as a regular RPM transaction event (Radek Holy)
- rename TransactionDisplay.event to TransactionDisplay.progress (Radek Holy)
- apichange: deprecate dnf.callback.LoggingTransactionDisplay (Radek Holy)
- use both CliTransactionDisplay and demands.transaction_display (Radek Holy)
- apichange: accept multiple displays in do_transaction (Radek Holy)
- support multiple displays in RPMTransaction (Radek Holy)

* Fri Jul 31 2015 Michal Luscon <mluscon@redhat.com> 1.0.2-3
- Fix regression in group list command introduced by 02c3cc3 (Adam Salih)
- AUTHORS: updated (Jan Silhan)
- stop saying "experimental" (Matthew Miller)

* Tue Jul 21 2015 Jan Silhan <jsilhan@redhat.com> 1.0.2-2
- fixed python3 syntax error from f427aa2 (Jan Silhan)

* Fri Jul 17 2015 Michal Luscon <mluscon@redhat.com> 1.0.2-1
- give --allowerasing hint when error occurs during resolution (RhBug:1148630)
  (Jan Silhan)
- show --best hint with skipped packages every time (RhBug:1176351) (Jan Silhan)
- notify about skipped packages when upgrade (RhBug:1210445) (Jan Silhan)
- dnf-automatic: Document apply_updates=no behavior wrt keepcache (Ville
  Skyttä)
- persistor: share functionality of JSONDB (Jan Silhan)
- keepcache=0 persists packages till next successful transaction
  (RhBug:1220074) (Jan Silhan)
- do not use releasever in cache path (related to RhBug:1173107) (Michael
  Mraka)
- doc: add dnf list use case (Michal Luscon)
- repo: allow ntlm proxy auth (RhBug:1219199) (Michal Luscon)
- add a script which updates release notes (Radek Holy)
- doc: reverse the order of release notes (Radek Holy)
- completion_helper: fix tb if list XXX is not known arg (RhBug:1220040) (Igor
  Gnatenko)
- configurable maximum number of parallel downloads (RhBug:1230975) (Igor
  Gnatenko)
- add info to bash_completion (1nsan3)
- dnf upgrade does not try to upgrade uninstalled packages (RhBug: 1234763)
  (Adam Salih)
- dnf group list now checks every package and prints out only invalid ones
  (Adam Salih)
- install: return zero exit code if group is already installed (RhBug:1232815)
  (Michal Luscon)
- doc: add -b which does the same as --best (Igor Gnatenko)
- support category groups (Michael Mraka)
- cli test update for repofrompath (Michael Mraka)
- documentation for --repofrompath (Michael Mraka)
- implemented --repofrompath option (RhBug:1113384) (Michael Mraka)
- doc: document filter provides and obsoletes (Michal Luscon)
- doc: extend --quiet explanation (RhBug:1133979) (Jan Silhan)
- fixed dnf-automatic email emitter unicode error (RhBug:1238958) (Jan Silhan)
- doc: be specific what 'available' means in list/info (Jan Silhan)
- cosmetic: fixed typo (RhBug:1238252) (Jan Silhan)
- groups: clean dependencies (Michal Luscon)
- groups: fix removing of env that contains previously removed group (Michal
  Luscon)
- groups: fix removing of empty group (Michal Luscon)
- AUTHORS: updated (Jan Silhan)
- bash-completion: ignore sqlite3 user configuration (Peter Simonyi)
- Fix package name for rawhide .repo files (Frank Dana)
- Add 'transaction_display' to DemandSheet (Will Woods)
- translation: update (Jan Silhan)
- translation: use zanata instead of transifex (Jan Silhan)
- Updated Polish translation (Piotr Drąg)
- updated georgian translation (George Machitidze)
- group: fixed installing of already installed environment (Jan Silhan)
- conf: change minrate threshold to librepo default (RhBug:1212320) (Michal
  Luscon)

* Tue Jun 09 2015 Michal Luscon <mluscon@redhat.com> 1.0.1-2
- conf: change minrate threshold to librepo default (RhBug:1212320)
- group: fixed installation of already installed environments

* Tue Jun 09 2015 Michal Luscon <mluscon@redhat.com> 1.0.1-1
- doc: document variables in repo conf (Michal Luscon)
- groups: temporary fix for group remove (RhBug:1214968) (Michal Luscon)
- group: print summary of marked groups / environments together at the end (Jan
  Silhan)
- group: fixed marking as installed (RhBug:1222694) (Jan Silhan)
- doc: Spelling fixes (Ville Skyttä)
- dnf-automatic: Fix systemd service description (thanks Ville Skyttä) (Jan
  Silhan)
- doc: assumeyes added to Base.conf and config option (Jan Silhan)
- optionparser: deleted --obsoletes option that conflicted with repoquery
  plugin (Jan Silhan)
- dnf-automatic: Document emit_via default (Ville Skyttä)
- man: yum2dnf don;t show content (RhBug:1225246) (Thanks Adam Salih) (Jan
  Silhan)
- doc: allowed chars of repo ID (Jan Silhan)
- doc: minimal repo config file (Jan Silhan)
- doc: configuration files replacement policy (Jan Silhan)
- fixed typo in man page (RhBug:1225168) (Michael Mraka)
- Update authors (Michal Luscon)
- dnf-automatic: add random_sleep option (RhBug:1213985) (Vladan Kudlac)
- don't print bug report statement when rpmdb is corrupted
  (Related:RhBug:1225277) (Jan Silhan)
- comps: fix unicode issue (RhBug:1223932) (Thanks Parag) (Parag Nemade)
- logging: setup librepo log in verbose mode (Michal Luscon)
- doc: document the versioning scheme (Radek Holy)
- groups: end up empty group removal before solving (Michal Luscon)
- groups: end up empty installation before solving (RhBug:1223614) (Michal
  Luscon)
- doc: add support for transactions/packages/ranges in "dnf history list"
  (Radek Holy)
- doc: add support for transaction ranges in "dnf history info" (Radek Holy)
- support ssl client certificates (RhBug:1203661) (Michael Mraka)
- doc: document the "mirrorlist" configuration option (Radek Holy)
- doc: document the "metalink" configuration option (Radek Holy)
- doc: document the "baseurl" configuration option (Radek Holy)
- doc: document the "enabled" configuration option (Radek Holy)
- doc: document the "name" configuration option (Radek Holy)
- Revert "spec: added sqlite requirement" (Jan Silhan)
- spec: added sqlite requirement (Jan Silhan)
- cosmetic: fixed typo in comment (Jan Silhan)
- man: added reference to bug reporting guide (Jan Silhan)
- test: ignore user terminal width (Jan Silhan)
- cosmetic: base: import dnf.util.first (Jan Silhan)
- base.upgrade: inform user when pkg not installed and skipped (RhBug:1187741)
  (Jan Silhan)
- disable buildtime c/c++ dependency (Michael Mraka)
- doc: document the new virtual provides (Radek Holy)
- AUTHORS: updated (Jan Silhan)
- AUTHORS: distuinguish authors and contributors (Jan Silhan)
- Create ka.po (George Machitidze)
- Parser: fix path handling (Haikel Guemar)
- doc: metadata_timer_sync checked every hour (Jan Silhan)

* Wed Apr 29 2015 Michal Luscon <mluscon@redhat.com> 1.0.0-1
- doc: release notes dnf-1.0.0 (Michal Luscon)
- completion: don't do aliases (RhBug:1215289) (Jan Silhan)
- use Sack.load_repo() instead of Sack.load_yum_repo() (Jan Silhan)
- Repo.name has default value of repo ID (RhBug:1215560) (Jan Silhan)
- cosmetic: get rid of user visible yum references (Jan Silhan)
- moved install_or_skip to dnf.comps (Jan Silhan)
- group: see already installed group during installation (RhBug:1199648) (Jan
  Silhan)
- group: install_or_skip returns num of packages to install (Jan Silhan)
- group: made global function install_or_skip (Jan Silhan)
- AUTHORS: updated (Radek Holy)
- describe --refresh option in --help output (Pádraig Brady)
- better no such command message (RhBug:1208773) (Jan Silhan)
- doc: package-cleanup example doesn't print 'No match for argument:...'
  garbage (Jan Silhan)
- mention yum check replacement (Michael Mraka)
- added ref to dnf list (Michael Mraka)
- added package-cleanup to dnf translation table (Michael Mraka)
- python3: Repo comparison (RhBug:1208018) (Jan Silhan)
- python3: YumHistoryRpmdbProblem comparison (RhBug:1207861) (Jan Silhan)
- python3: YumHistoryTransaction comparison (Jan Silhan)
- tests: use packages in test_transaction (Radek Holy)
- cosmetic: fix some Pylint errors (Radek Holy)
- updated documentation wrt installonlypkgs and auto removal (Michael Mraka)
- mark installonly packages always as userinstalled (RhBug:1201445) (Michael
  Mraka)
- mark username/password as api (Michael Mraka)
- document username/password repo attributes (Michael Mraka)
- support HTTP basic auth (RhBug:1210275) (Michael Mraka)
- cli: better metadata timestamp info (Michal Luscon)
- repo: add metadata mirror failure callback (Michal Luscon)
- dnf-yum: cosmetic: lower case after comma (Jan Silhan)
- dnf-yum: print how to install migrate plugin (Jan Silhan)
- doc: show the real package for each tool in dnf-plugins-extras (Tim
  Lauridsen)
- doc: improve the documentation of repo costs (Radek Holy)
- doc: fix debuginfo-install package name (Michal Luscon)
- doc: release notes 0.6.5 (Michal Luscon)
- bash-completion: allow only one subcmd for help (Igor Gnatenko)
- bash-completion: add history completion (Igor Gnatenko)
- bash-completion: add completion for help (Igor Gnatenko)
- bash-completion: check where pointing bin/dnf (Igor Gnatenko)
- bash-completion: implement completion for clean cmd (Igor Gnatenko)
- bash_completion: implement downgrade command (Igor Gnatenko)
- bash-completion: refactor to python helper (Igor Gnatenko)
- command downgrade does downgrade_to (RhBug:1191275) (Jan Silhan)
- AUTHORS: updated (Jan Silhan)
- clean: 'dnf clean all' should also clean presto and updateinfo solvx files
  (Parag Nemade)
- dnf-yum: modified warning message (RhBug:1207965) (Jan Silhan)

* Tue Mar 31 2015 Michal Luscon <mluscon@redhat.com> 0.6.5-1
- subject: expand every glob name only once (RhBug:1203151) (Michal Luscon)
- group mark: skips already installed groups (Jan Silhan)
- Merge pull request #246 from mluscon/yum2dnf (mluscon)
- Add yum2dnf man page (Michal Luscon)
- doc: extend cli_vs_yum (Michal Luscon)
- dnf-yum package does not conflict with yum 3.4.3-505+ (Jan Silhan)
- fixed double set of demand from 0e4276f (Jan Silhan)
- group: remove cmd don't load available_repos, see 04da412 (Jan Silhan)
- spec: /var/lib/dnf owned by dnf-conf (Jan Silhan)
- spec: apply the weak dependencies only on F21+ (Radek Holy)
- dnf-automatic: fixed python_sitelib (RhBug:1199450) (Jan Silhan)
- Add release instructions (Michal Luscon)
- setup tito to bump version in VERSION.cmake (Michal Luscon)
- initialize to use tito (Michal Luscon)
- prepare repo for tito build system (Michal Luscon)
- spec: recommends bash-completion (RhBug:1190671) (Jan Silhan)
- completion: work with just python(3)-dnf (Jan Silhan)
- spec: move necessary files inside python(3) subpackages (RhBug:1191579) (Jan Silhan)
- bash-completion: use python method to get commands (RhBug:1187579) (Igor Gnatenko)
- api: exposed pluginconfpath main config (RhBug:1195325) (Jan Silhan)
- updated AUTHORS (Jan Silhan)
- add reinstall to bash_completion (Alberto Ruiz)
- added new packages to @System for duplicated query test (Michael Mraka)
- test for duplicated, installonly and latest_limit pkgs (Michael Mraka)
- tests for autoremove, extras and recent pkgs (Michael Mraka)
- moved push_userinstalled from base to goal (Michael Mraka)
- filter or skip 'n' latest packages (Michael Mraka)
- moved recent to query (Michael Mraka)
- moved autoremove to query (Michael Mraka)
- moved extras list to query (Michael Mraka)
- create query for installonly packages (Michael Mraka)
- create query for duplicated packages (Michael Mraka)
- cosmetic: base: fixed pylint warnings (Jan Silhan)
- do transaction cleanup after plugin hook (RhBug:1185977) (Michal Luscon)
- base: extend download lock (RhBug:1157233) (Michal Luscon)
- lock: output meaningful error for malformed lock file (Michal Luscon)
- util: fix race condition in ensure_dir() (Michal Luscon)
- lock: switch metadata lock to blocking mode (Michal Luscon)
- install nonmandatory group packages as optional (Related:RhBug:1167881) (Michal Luscon)
- remove command deletes whole dependency tree (RhBug:1154202) (Jan Silhan)
- cmd list takes <package-name-specs> as parameter, revert of 526e674 (Jan Silhan)
- spec: own /var/lib/dnf directory (RhBug:1198999) (Jan Silhan)
- transifex update (Jan Silhan)
- doc: fixed systemd execution of dnf-automatic (Jan Silhan)
- doc: how to run dnf-automatic (RhBug:1195240) (Jan Silhan)
- cosmetic: added forgotten :api mark from 05b03fc (Jan Silhan)
- api: exposed Repo.skip_if_unavailable config (RhBug:1189083) (Jan Silhan)
- updated documentation for 'dnf list autoremove' (Michael Mraka)
- reuse list_autoremove() in autoremove command (Michael Mraka)
- function for autoremove package list (Michael Mraka)
- implemented dnf list autoremove (Michael Mraka)
- exclude not documented history subcommands (RhBug:1193914,1193915) (Jan Silhan)
- better file pattern recognition (RhBug:1195385) (Jan Silhan)
- spec: fix Obsoletes of the new DNF (Radek Holy)
- remove boot only constraint and add missing download lock (Michal Luscon)
- util: remove unused user_run_dir() function (Michal Luscon)
- lock: change the destination folder of locks to allow suided programs work properly (RhBug:1195661) (Michal Luscon)
- install dnf-3 only when python3 is enabled (thanks glensc) (Jan Silhan)
- fixed unicode Download error (RhBug:1190458) (Jan Silhan)
- log: print metadata age along with timestamp (Petr Spacek)
- cli: fix double expansion of cachedir (RhBug:1194685) (Michal Luscon)
- removed unused dnf-makecache.cron (Jan Silhan)
- renamed erase command to remove (RhBug:1160806) (Jan Silhan)
- spec: made python3-dnf package installed by default in f23 (Jan Silhan)
- AUTHORS: changed email address (Jan Silhan)
- doc: improve the documentation of the "install" command (Radek Holy)
- "dnf install non-existent" should fail (Radek Holy)
- tests: add some tests of Base.install (Radek Holy)
- tests: add some tests of Base.package_install (Radek Holy)
- Revert "doesn't upgrade packages by installing local packages" (RhBug:1160950) (Radek Holy)
- lint: fix all Pylint errors in test_install (Radek Holy)
- tests: add some tests to test_install (Radek Holy)
- tests: improve some tests in test_install (Radek Holy)
- cosmetic: reorder tests in test_install (Radek Holy)
- cosmetic: rename some tests in test_install and add some docstrings (Radek Holy)
- AUTHORS: updated (Jan Silhan)
- Add support for armv6hl (Peter Hjalmarsson)
- doc: subject.__init__(): what is pkg_spec (Jan Silhan)
- doc: mentioning raising IOError from Base.fill_sack() (Jan Silhan)
- option_parser: fixed splitting multiple values (RhBug:1186710) (Jan Silhan)
- AUTHORS: updated (Jan Silhan)
- Standardize words describing boolean data type (Christopher Meng)

* Wed Feb 4 2015 Jan Silhan <jsilhan@redhat.com> - 0.6.4-1
- Adapt to librepo-1.7.13, metalink and mirrorlist are not loaded anymore when the repo is local. (Radek Holy)
- not raises value error when no metadata exist (Jan Silhan)
- Remove lock files during boot (RhBug:1154476) (Michal Luscon)
- doc: groups are ordered not categories (Jan Silhan)
- doc: added Package attributes to API (Jan Silhan)
- README: link to bug reporting guide (Jan Silhan)
- README: the official documentation is on readthedoc (Jan Silhan)
- i18n: unicode encoding does not throw error (RhBug:1155877) (Jan Silhan)
- conf: added minrate repo option (Related:RhBug:1175466) (Jan Silhan)
- conf: added timeout repo option (RhBug:1175466) (Jan Silhan)
- doc: api_queries: add 'file' filter description (RhBug:1186461) (Igor Gnatenko)
- doc: documenting enablegroups (Jan Silhan)
- log: printing metadata timestamp (RhBug:1170156) (Jan Silhan)
- base: setup default cachedir value (RhBug:1184943) (Michal Luscon)
- orders groups/environments by display_order tag (RhBug:1177002) (Jan Silhan)
- no need to call create_cmdline_repo (Jan Silhan)
- base: package-spec matches all packages which the name glob pattern fits (RhBug:1169165) (Michal Luscon)
- doc: move dnf.conf to appropriate man page section (RhBug:1167982) (Michal Luscon)
- tests: add test for blocking process lock (Michal Luscon)
- lock: fix several race conditions in process lock mechanism (Michal Luscon)
- base: use blocking process lock during download phase (RhBug:1157233) (Michal Luscon)
- Update the Source0 generation commands in dnf.spec.in file (Parag Nemade)
- Enhancement to dnf.spec.in file which follows current fedora packaging guidelines (Parag Nemade)
- doc: add some examples and documentation of the core use case (RhBug:1138096) (Radek Holy)
- bash-completion: enable downgrading packages for local files (RhBug:1181189) (Igor Gnatenko)
- group: prints plain package name when package not in any repo (RhBug:1181397) (Jan Silhan)
- spec: own __pycache__ for python 3 (Igor Gnatenko)
- changed hawkey.log dir to /var/log (RhBug:1175434) (Jan Silhan)
- bash-completion: handle sqlite errors (Igor Gnatenko)
- use LANG=C when invoking 'dnf help' and 'sed' with regular expressions (Jakub Dorňák)
- spec: own __pycache__ directory for py3 (Igor Gnatenko)
- doc: mentioning Install command accepts path to local rpm package (Jan Silhan)
- groups: in erase and install cmd non-existent group does not abort transaction (Jan Silhan)
- doc: running tests in README (Jan Silhan)
- api: transaction: added install_set and remove_set (RhBug:1162887) (Jan Silhan)
- cosmetic: fixed some typos in documentation (Jan Silhan)
- groups: environments described after @ sign works (RhBug:1156084) (Jan Silhan)
- own /etc/dnf/protected.d (RhBug:1175098) (Jan Silhan)
- i18n: computing width of char right (RhBug:1174136) (Jan Silhan)
- cosmetic: renamed _splitArg -> _split_arg (Jan Silhan)
- conf: removed include name conflict (RhBug:1055910) (Jan Silhan)
- output: removed unpredictible decision based on probability introduced in ab4d2c5 (Jan Silhan)
- output: history list is not limited to 20 records (RhBug:1155918) (Jan Silhan)
- doc: referenced forgotten bug fix to release notes (Jan Silhan)
- cosmetic: doc: removed duplicated word (Jan Silhan)
- doc: described unavailable package corner case with skip_if_unavailable option (RhBug:1119030) (Jan Silhan)
- log: replaced size with maxsize directive (RhBug:1177394) (Jan Silhan)
- spec: fixed %ghost log file names (Jan Silhan)

* Mon Dec 8 2014 Jan Silhan <jsilhan@redhat.com> - 0.6.3-2
- logging: reverted naming from a6dde81

* Mon Dec 8 2014 Jan Silhan <jsilhan@redhat.com> - 0.6.3-1
- transifex update (Jan Silhan)
- bash-completion: don't query if we trying to use local file (RhBug:1153543) (Igor Gnatenko)
- bash-completion: fix local completion (RhBug:1151231) (Igor Gnatenko)
- bash-completion: use sqlite cache from dnf-plugins-core (Igor Gnatenko)
- base: output a whole list of installed packages with glob pattern (RhBug:1163063) (Michal Luscon)
- cli: _process_demands() does not respect --caheonly (RhBug:1151854) (Michal Luscon)
- new authors added (Jan Silhan)
- install: allow installation of provides with glob (Related:RhBug:1148353) (Michal Luscon)
- tests: removed mock patch for _, P_ (Jan Silhan)
- fixed error summary traceback (RhBug:1151740) (Jan Silhan)
- doc: swap command alternative mentioned (RhBug:1110780) (Jan Silhan)
- base: package_reinstall works only with the same package versions (Jan Silhan)
- base: package_install allows install different arch of installed package (Jan Silhan)
- base: package_downgrade prints message on failure (Jan Silhan)
- base: package_upgrade does not reinstall or downgrade (RhBug:1149972) (Jan Silhan)
- groups: searches also within localized names (RhBug:1150474) (Jan Silhan)
- Run tests with C locales. (Daniel Mach)
- Adds new motd emitter for dnf-automatic (RhBug:995537) (Kushal Das)
- Fix wrong cache directory path used to clean up binary cache (Satoshi Matsumoto)
- fix: traceback in history info <name> (RhBug: 1149952) (Tim Lauridsen)
- logging: added logrotate script for hawkey.log (RhBug:1149350) (Jan Silhan)
- output: renamed displayPkgsInGroups (Jan Silhan)
- logging: renamed log files (RhBug:1074715)" (Jan Silhan)
- comps: Environment differentiates optional and mandatory groups (Jan Silhan)
- group info handles environments (RhBug:1147523) (Jan Silhan)
- deltarpm enabled by default (RhBug:1148208) (Jan Silhan)
- doc: deplist command (Jan Silhan)
- doc: minor fixes + repo references changed (Jan Silhan)
- spec: requires rpm-plugin-systemd-inhibit (RhBug:1109927) (Jan Silhan)

* Fri Oct 3 2014 Jan Silhan <jsilhan@redhat.com> - 0.6.2-1
- transifex update (Jan Silhan)
- refactor: move MakeCacheCommand out into its own file. (Ales Kozumplik)
- api: add dnf.cli.CliError. (Ales Kozumplik)
- Update user_faq.rst (Stef Krie)
- Make --refresh play nice with lazy commands. (Ales Kozumplik)
- bash-completion: more faster completing install/remove (Igor Gnatenko)
- bash-completion: complete 'clean|groups|repolist' using help (Igor Gnatenko)
- Allow some commands to use stale metadata. (RhBug:909856) (Ales Kozumplik)
- does not install new pkgs when updating from local pkgs (RhBug:1134893) (Jan Silhan)
- doesn't upgrade packages by installing local packages (Related:RhBug:1138700) (Jan Silhan)
- refactor: repo: separate concepts of 'expiry' and 'sync strategy'. (Ales Kozumplik)
- fix: dnf.cli.util.* leaks file handles. (Ales Kozumplik)
- remove: YumRPMTransError. (Ales Kozumplik)
- rename: Base's runTransaction -> _run_transaction(). (Ales Kozumplik)
- drop unused parameter of Base.verify_transaction(). (Ales Kozumplik)
- bash-completion: new completion from scratch (RhBug:1070902) (Igor Gnatenko)
- py3: add queue.Queue to pycomp. (Ales Kozumplik)
- locking: store lockfiles with the resource they are locking. (RhBug:1124316) (Ales Kozumplik)
- groups: marks reason 'group' for packages that have no record yet (RhBug:1136584) (Jan Silhan)
- goal: renamed undefined name variable (Jan Silhan)
- refactor: split out and clean up the erase command. (Ales Kozumplik)
- py3: fix traceback in fmtColumns() on a non-subscriptable 'columns'. (Ales Kozumplik)
- groups: allow erasing depending packages on remove (RhBug:1135861) (Ales Kozumplik)
- history: fixed wrong set operation (RhBug:1136223) (Jan Silhan)
- base: does not reinstall pkgs from local rpms with install command (RhBug:1122617) (Jan Silhan)
- refactor: crypto: drop the integer keyid representation altogether. (Ales Kozumplik)
- crypto: fix importing rpmfusion keys. (RhBug:1133830) (Ales Kozumplik)
- refactor: crypto: Key is a class, not an "info" dict. (Ales Kozumplik)
- repos: fix total downloaded size reporting for cached packages. (RhBug:1121184) (Ales Kozumplik)

* Thu Aug 28 2014 Jan Silhan <jsilhan@redhat.com> - 0.6.1-1
- packaging: add dnf-yum. (Ales Kozumplik)
- cli: added plugins missing hint (RhBug:1132335) (Jan Silhan)
- using ts.addReinstall for package reinstallation (RhBug:1071854) (Jan Silhan)
- Add history redo command. (Radek Holy)
- Add a TransactionConverter class. (Radek Holy)
- bash-completion: complete `help` with commands (Igor Gnatenko)
- bash-completion: generate commands dynamically (Igor Gnatenko)
- base: group_install accepts glob exclude names (RhBug:1131969) (Jan Silhan)
- README: changed references to new repo location (Jan Silhan)
- transifex update (Jan Silhan)
- syntax: fixed indentation (Jan Silhan)
- removed lt.po which was accidentally added in c2e9b39 (Jan Silhan)
- lint: fix convention violations in the new source files (Radek Holy)
- Fix setting of the resolving demand for repo-pkgs command. (Radek Holy)
- Add repository-packages remove-or-distro-sync command. (RhBug:908764) (Radek Holy)
- fix: traceback that GroupPersistor._original might not exist. (RhBug:1130878) (Ales Kozumplik)
- pycomp: drop to_ord(). (Ales Kozumplik)
- refactor: crypto.keyids_from_pubring() using _extract_signing_subkey(). (Ales Kozumplik)
- fix: another 32-bit hex() problem in crypto. (Ales Kozumplik)
- remove: pgpmsg.py. (Ales Kozumplik)
- replace the whole of pgpmsg.py with gpgme and a dummy context. (Ales Kozumplik)
- cosmetic: sort methods of Repo according to the coding standard. (Ales Kozumplik)
- Fix dnf.crypto.keyinfo2keyid(). (Ales Kozumplik)
- util: get rid of an inconvenient 'default_handle' constant. (Ales Kozumplik)
- simplify misc.import_key_to_pubring()'s signature. (Ales Kozumplik)
- cleanup: header of dnf.yum.pgpmsg. (Ales Kozumplik)
- crypto: add crypto.retrieve() and drop Base._retrievePublicKey() (Ales Kozumplik)
- cosmetic: order of functions in dnf.crypto. (Ales Kozumplik)
- unicode: fixed locale.format error (RhBug:1130432) (Jan Silhan)
- remove: misc.valid_detached_sig(). (Ales Kozumplik)
- tests: some tests for dnf.crypto. (Ales Kozumplik)
- crypto: use pubring_dir() context manager systematically. (Ales Kozumplik)
- Drop unused argument from getgpgkeyinfo(). (Ales Kozumplik)
- remove: Base._log_key_import(). (Ales Kozumplik)
- doc: cosmetic: conf_ref: maintain alphabetical order of the options. (Ales Kozumplik)
- crypto: document crypto options for repo. (Ales Kozumplik)
- crypto: fixup procgpgkey() to work with Py3 bytes. (Ales Kozumplik)
- dnf.util.urlopen(): do not create unicode streams for Py3 and bytes for Py2 by default. (Ales Kozumplik)
- lint: delinting of the repo_gpgcheck patchset. (Ales Kozumplik)
- Add CLI parts to let the user confirm key imports. (RhBug:1118236) (Ales Kozumplik)
- gpg: make key decoding work under Py3. (Ales Kozumplik)
- crypto: add dnf.crypto and fix things up so untrusted repo keys can be imported. (Ales Kozumplik)
- transifex update (Jan Silhan)
- syntax: fixed indentation (Jan Silhan)
- packaging: pygpgme is a requirement. (Ales Kozumplik)
- remove: support for gpgcakey gets dropped for now. (Ales Kozumplik)
- repo: smarter _DetailedLibrepoError construction. (Ales Kozumplik)
- repo: nicer error message on librepo's perform() failure. (Ales Kozumplik)
- get_best_selector returns empty selector instead of None (Jan Silhan)
- packaging: add automatic's systemd unit files. (RhBug:1109915) (Ales Kozumplik)
- automatic: handle 'security' update_cmd. (Ales Kozumplik)

* Tue Aug 12 2014 Aleš Kozumplík <ales@redhat.com> - 0.6.0-1
- lint: fix convention violations in the new source files (Radek Holy)
- Add "updateinfo [<output>] [<availability>] security" command. (RhBug:850912) (Radek Holy)
- Add "updateinfo [<output>] [<availability>] bugfix" command. (Radek Holy)
- Add "updateinfo [<output>] [<availability>] enhancement" command. (Radek Holy)
- Add "updateinfo [<output>] [<availability>] [<package-name>...]" command. (Radek Holy)
- Add "updateinfo [<output>] [<availability>] [<advisory>...]" command. (Radek Holy)
- Add "updateinfo [<output>] all" command. (Radek Holy)
- Add "updateinfo [<output>] updates" command. (Radek Holy)
- Add "updateinfo [<output>] installed" command. (Radek Holy)
- Add "-v updateinfo info" command. (Radek Holy)
- Add "updateinfo info" command. (Radek Holy)
- Add "updateinfo list" command. (Radek Holy)
- Add "updateinfo available" command. (Radek Holy)
- Add "updateinfo summary" command. (Radek Holy)
- Add basic updateinfo command. (Radek Holy)
- test: add updateinfo to the testing repository (Radek Holy)
- test: support adding directory repos to Base stubs (Radek Holy)
- test: really don't break other tests with the DRPM fixture (Radek Holy)
- Load UpdateInfo.xml during the sack preparation. (Radek Holy)
- Add Repo.updateinfo_fn. (Radek Holy)
- lint: add Selector calls to false positives, it's a hawkey type. (Ales Kozumplik)
- removed recursive calling of ucd in DownloadError (Jan Silhan)
- does not throw error when selector is empty (RhBug:1127206) (Jan Silhan)
- remove etc/version-groups.conf, not used. (Ales Kozumplik)
- lint: dnf.conf.parser (Ales Kozumplik)
- rename: dnf.conf.parser.varReplace()->substitute() (Ales Kozumplik)
- pycomp: add urlparse/urllib.parser. (Ales Kozumplik)
- move: dnf.yum.parser -> dnf.conf.parser. (Ales Kozumplik)
- packaging: add dnf-automatic subpackage. (Ales Kozumplik)
- doc: properly list the authors. (Ales Kozumplik)
- automatic: add documentation, including dnf.automatic(8) man page. (Ales Kozumplik)
- dnf-automatic: tool supplying the yum-cron functionality. (Ales Kozumplik)
- doc: cosmetic: fixed indent in proxy directive (Jan Silhan)
- include directive support added (RhBug:1055910) (Jan Silhan)
- refactor: move MultiCallList to util. (Ales Kozumplik)
- cli: do not output that extra starting newline in list_transaction(). (Ales Kozumplik)
- refactor: extract CLI cachedir magic to cli.cachedir_fit. (Ales Kozumplik)
- transifex update (Jan Silhan)
- move: test_output to tests/cli. (Ales Kozumplik)
- refactor: move Term into its own module. (Ales Kozumplik)
- refactoring: cleanup and linting in dnf.exceptions. (Ales Kozumplik)
- lint: test_cli.py (Ales Kozumplik)
- lint: rudimentary cleanups in tests.support. (Ales Kozumplik)
- refactor: loggers are module-level variables. (Ales Kozumplik)
- groups: promote unknown-reason installed packages to 'group' on group install. (RhBug:1116666) (Ales Kozumplik)
- c82267f refactoring droppped plugins.run_transaction(). (Ales Kozumplik)
- cli: sort packages in the transaction summary. (Ales Kozumplik)
- refactor: cli: massively simplify how errors are propagated from do_transaction(). (Ales Kozumplik)
- groups: rearrange things in CLI so user has to confirm the group changes. (Ales Kozumplik)
- groups: committing the persistor data should only happen at one place. (Ales Kozumplik)
- groups: visualizing the groups transactions. (Ales Kozumplik)
- Add dnf.util.get_in() to navigate nested dicts with sequences of keys. (Ales Kozumplik)
- group persistor: generate diffs between old and new DBs. (Ales Kozumplik)
- Better quoting in dnf_pylint. (Ales Kozumplik)
- lint: logging.py. (Ales Kozumplik)
- Do not print tracebacks to the tty on '-d 10' (RhBug:1118272) (Ales Kozumplik)
- search: do not double-report no matches. (Ales Kozumplik)
- refactor: move UpgradeToCommand to its own module. (Ales Kozumplik)

* Mon Jul 28 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.5-1
- packaging: also add pyliblzma to BuildRequires. (Ales Kozumplik)
- essential cleanup in dnf.yum.misc, removing a couple of functions too. (Ales Kozumplik)
- remove: Base.findDeps and friends. (Ales Kozumplik)
- Make pyliblzma a requriement. (RhBug:1123688) (Ales Kozumplik)
- whole user name can contain non-ascii chars (RhBug:1121280) (Jan Silhan)
- Straighten up the exceptions when getting a packages header. (RhBug:1122900) (Ales Kozumplik)
- tests: refactor: rename test_resource_path() -> resource_path() and use it more. (Ales Kozumplik)
- transifex update (Jan Silhan)
- remove: conf.commands. (Ales Kozumplik)
- proxy username and password, for both CLI and API. (RhBug:1120583) (Ales Kozumplik)
- conf: only 'main' is a reserved section name. (Ales Kozumplik)
- refactoring: cleanup a couple of lint warnings in base.py. (Ales Kozumplik)
- refactoring: move repo reading implementation out of dnf.Base. (Ales Kozumplik)
- refactor: repo_setopts is a CLI thing and doesn't belong to Base. (Ales Kozumplik)
- refactor: move cleanup methods to dnf.cli.commands.clean. (Ales Kozumplik)
- depsolving: doesn't install both architectures of pkg by filename (RhBug:1100946) (Jan Silhan)
- refactor: put CleanCommand in its own module. (Ales Kozumplik)
- cli: avoid 'Error: None' output on malformed CLI commands. (Ales Kozumplik)
- remove the special SIGQUIT handler. (Ales Kozumplik)
- api: In Repo(), cachedir is a required argument. (Ales Kozumplik)
- api: better describe how Repos should be created, example. (RhBug:1117789) (Ales Kozumplik)
- Base._conf lasts the lifetime of Base and can be passed via constructor. (Ales Kozumplik)
- doc: faq: having Yum and DNF installed at the same time. (Ales Kozumplik)
- remove: protected_packages config option, it has been ignored. (Ales Kozumplik)
- fix: misleading error message when no repo is enabled. (Ales Kozumplik)

* Wed Jul 16 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.4-1
- pkg name from rpm transaction callback is in Unicode (RhBug:1118796) (Jan Silhan)
- packaging: python3-dnf depends on dnf. (RhBug:1119032) (Ales Kozumplik)
- Ship /usr/bin/dnf-3 to run DNF under Py3. (RhBug:1117678) (Ales Kozumplik)
- packaging: own /etc/dnf/plugins. (RhBug:1118178) (Ales Kozumplik)
- fix: pluginconfpath is a list. (Ales Kozumplik)
- cosmetic: use classmethod as a decorator in config.py. (Ales Kozumplik)
- cleanup: imports in dnf.cli.output (Ales Kozumplik)
- lint: straightforward lint fixes in dnf.cli.output. (Ales Kozumplik)
- Repo.__setattr__ has to use the parsed value. (Ales Kozumplik)
- Repo priorities. (RhBug:1048973) (Ales Kozumplik)
- repo: simplify how things are propagated to repo.hawkey_repo. (Ales Kozumplik)
- refactor: concentrate Repo.hawkey_repo construction in Repo.__init__(). (Ales Kozumplik)
- bash-completion: Update command and option lists, sort in same order as --help (Ville Skyttä)
- bash-completion: Use grep -E instead of deprecated egrep (Ville Skyttä)
- output: fixed identation of info command output (Jan Silhan)
- i18n: calculates right width of asian utf-8 strings (RhBug:1116544) (Jan Silhan)
- transifex update + renamed po files to Fedora conventions (Jan Silhan)
- remove: CLI: --randomwait (Ales Kozumplik)
- cli: fix: --installroot has to be used with --releasever (RhBug:1117293) (Ales Kozumplik)
- Base.reset(goal=True) also resets the group persistor (RhBug:1116839) (Ales Kozumplik)
- tests: fix failing DistroSync.test_distro_sync(). (Ales Kozumplik)
- logging: RPM transaction markers are too loud. (Ales Kozumplik)
- logging: silence drpm a bit. (Ales Kozumplik)
- logging: put timing functionality into one place. (Ales Kozumplik)
- repolist: fix traceback with disabled repos. (RhBug:1116845) (Ales Kozumplik)
- refactor: cleanups in repolist. (Ales Kozumplik)
- lint: remove some unused imports. (Ales Kozumplik)
- cli: break out the repolsit command into a separate module. (Ales Kozumplik)
- does not crash with non-ascii user name (RhBug:1108908) (Jan Silhan)
- doc: document 'pluginpath' configuration option. (RhBug:1117102) (Ales Kozumplik)
- Spelling fixes (Ville Skyttä)
- cli: Fix software name in --version help (Ville Skyttä)
- doc: ip_resolve documented at two places. remove one. (Ales Kozumplik)

* Thu Jul 3 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.3-1
- packaging: bump hawkey dep to 0.4.17. (Ales Kozumplik)
- api: remove Base.select_group(). (Ales Kozumplik)
- tests: cleanup our base test case classes a bit. (Ales Kozumplik)
- Add DNF itself among the protected packages. (Ales Kozumplik)
- api: plugins: add the resolved() hook. (Ales Kozumplik)
- api: expose Transaction introspecting in the API. (RhBug:1067156) (Ales Kozumplik)
- api: add basic documentation for dnf.package.Package. (Ales Kozumplik)
- tests: cosmetic: conf.protected_packages is ignored, drop it in FakeConf. (Ales Kozumplik)
- cli: simplify exception handling more. (Ales Kozumplik)
- Fixed a minor typo in user_faq - 'intall' should be 'install' (Martin Preisler)
- fixed encoding of parsed config line (RhBug:1110800) (Jan Silhan)
- syntax: replaced tab with spaces (Jan Silhan)
- doc: acknowledge the existence of plugins on the man page (RhBug:1112669) (Ales Kozumplik)
- improve the 'got root?' message of why a transaction couldn't start. (RhBug:1111569) (Ales Kozumplik)
- traceback in Base.do_transaction. to_utf8() is gone since 06fb280. (Ales Kozumplik)
- fix traceback from broken string formatting in _retrievePublicKey(). (RhBug:1111997) (Ales Kozumplik)
- doc: replace Yum with DNF in command_ref.rst (Viktor Ashirov)
- Fix a missing s in the title (mscherer)
- api: add dnf.rpm.detect_releasever() (Ales Kozumplik)
- Detect distroverpkg from 'system-release(release)' (RhBug:1047049) (Ales Kozumplik)
- bulid: add dnf/conf to cmake. (Ales Kozumplik)
- lint: clean up most lint messages in dnf.yum.config (Ales Kozumplik)
- remove: couple of dead-code methods in dnf.yum.config. (Ales Kozumplik)
- api: document client's responsibility to preset the substitutions. (RhBug:1104757) (Ales Kozumplik)
- move: rpmUtils -> rpm. (Ales Kozumplik)
- refactor: move yumvar out into its proper module dnf.conf.substitutions. (Ales Kozumplik)
- refactor: turn dnf.conf into a package. (Ales Kozumplik)
- doc: api_base.rst pointing to nonexistent method. (Ales Kozumplik)
- remove: some logging from Transaction.populate_rpm_ts(). (Ales Kozumplik)
- Update cli_vs_yum.rst (James Pearson)
- api: doc: queries relation specifiers, with an example. (RhBug:1105009) (Ales Kozumplik)
- doc: phrasing in ip_resolve documentation. (Ales Kozumplik)
- cli: refactored transferring cmdline options to conf (Jan Silhan)
- cli: added -4/-6 option for using ipv4/ipv6 connection (RhBug:1093420) (Jan Silhan)
- cosmetic: empty set inicialization (Jan Silhan)
- repo: improve the RepoError message to include URL. (Ales Kozumplik)
- remove: dnf.yum.config.writeRawRepoFile(). (Ales Kozumplik)
- remove: bunch of (now) blank config options. (Ales Kozumplik)
- removed unique function (Jan Silhan)
- tests: mock.assert_has_calls() enforces its iterable arguments in py3.4. (Ales Kozumplik)
- logging: improve how repolist logs the total number of packages. (Ales Kozumplik)
- logging: Base.close() should not log to the terminal. (Ales Kozumplik)

* Wed May 28 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.2-1
- doc: packaging: add license block to each .rst. (Ales Kozumplik)
- cosmetic: replaced yum with dnf in comment (Jan Silhan)
- takes non-ascii cmd line input (RhBug:1092777) (Jan Silhan)
- replaced 'unicode' conversion functions with 'ucd' (RhBug:1095861) (Jan Silhan)
- using write_to_file py2/py3 compatibility write function (Jan Silhan)
- encoding: all encode methods are using utf-8 coding instead of default ascii (Jan Silhan)
- fixed rpmbuild warning of missing file (Jan Silhan)
- transifex update (Jan Silhan)
- fixed typos in comments (Jan Silhan)
- Drop --debugrepodata and susetags generation with it. (Ales Kozumplik)
- doc: document --debugsolver. (Ales Kozumplik)
- fix: 'dnf repo-pkgs' failures (RhBug:1092006) (Radek Holy)
- lint: make dnf_pylint take '-s' that suppresses line/column numbers. (Ales Kozumplik)
- doc: cli_vs_yum: we do not promote installs to the obsoleting package. (RhBug:1096506) (Ales Kozumplik)
- dealing with installonlies, we always need RPMPROB_FILTER_OLDPACKAGE (RhBug:1095580) (Ales Kozumplik)
- transifex update (Jan Silhan)
- arch: recognize noarch as noarch's basearch. (RhBug:1094594) (Ales Kozumplik)
- pylint: clean up dnf.repo. (Ales Kozumplik)
- sslverify: documentation and bumped librepo require. (Ales Kozumplik)
- repos: support sslverify setting. (RhBug:1076045) (Ales Kozumplik)
- search: exact matches should propagate higher. (RhBug:1093888) (Ales Kozumplik)
- refactor: concentrate specific search functionality in commands.search. (Ales Kozumplik)
- refactor: SearchCommand in its own file. (Ales Kozumplik)
- pylint: fix around one hundred pylint issues in dnf.base. (Ales Kozumplik)
- pylint: add simple pylint script (Ales Kozumplik)
- autoerase: write out the debugdata used to calculate redundant packages. (Ales Kozumplik)
- cosmetic: fix pylint comment in test_group.py. (Ales Kozumplik)
- refactor: err_mini_usage() is public. (Ales Kozumplik)
- refactor: fix several pylint errors in dnf.cli.commands.group. (Ales Kozumplik)
- fix: 'dnf remove' is deprecated so autoremove should be autoerase. (Ales Kozumplik)
- doc: command_ref: remove the deprecated aliases from the initial list. (Ales Kozumplik)
- Add autoremove command. (RhBug:963345) (Ales Kozumplik)
- refactor: Base.push_userinstalled() is public. (Ales Kozumplik)
- Remove sudo from dnf-completion.bash RhBug:1073457 (Elad Alfassa)
- exclude switch takes <package-spec> as a parameter (Jan Silhan)
- using nevra glob query during list command (RhBug:1083679) (Jan Silhan)
- removed rpm.RPMPROB_FILTER_REPLACEOLDFILES filter flag (Jan Silhan)
- test: changed tests according to new distro-sync behavior (Jan Silhan)
- packaging: cosmetic: copyright years in bin/dnf. (Ales Kozumplik)
- bin/dnf: run the python interpreter with -OO. (Ales Kozumplik)

* Fri May 2 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.1-1
- drpm: output stats (RhBug:1065882) (Ales Kozumplik)
- refactor: architectures. (Ales Kozumplik)
- cli: be lot less verbose about dep processing. (Ales Kozumplik)
- groups: do not error out if group install/remove produces no RPM transaction. (Ales Kozumplik)
- fix: do not traceback on comps remove operations if proper pkg reasons can not be found. (Ales Kozumplik)
- fix: tracebacks in 'group remove ...' (Ales Kozumplik)
- groups: move all the logic of persistor saving from main.py to Base. (Ales Kozumplik)
- groups: auto-saving the groups persistor. (RhBug:1089864) (Ales Kozumplik)
- transifex update (Jan Silhan)
- remove: profiling code from cli.main. (Ales Kozumplik)
- remove: removal of dead code (Miroslav Suchý)
- doc: changes to rhbug.py to work on readthedocs.org. (Ales Kozumplik)
- doc: build the documentation without any dependencies (on DNF or anything else). (Ales Kozumplik)
- doc: make clear where one should expect bin/dnf (Miroslav Suchý)
- abrt: disable abrt for 'dnf makecache timer' run from systemd.service. (RhBug:1081753) (Ales Kozumplik)
- remove: stray itertools import from group.py. (Ales Kozumplik)

* Wed Apr 23 2014 Aleš Kozumplík <ales@redhat.com> - 0.5.0-1
- doc: fix formatting in api_cli.rst. (Ales Kozumplik)
- doc: document operation of 'group upgrade'. (Ales Kozumplik)
- comps: ensure only packages of 'group' reason get deleted on 'group erase'. (Ales Kozumplik)
- comps: store 'group' reason when installing a group-membering package. (Ales Kozumplik)
- Override Goal.get_reason(). (Ales Kozumplik)
- Add dnf.goal.Goal deriving from hawkey.Goal. (Ales Kozumplik)
- fix: encoding of yumdb directory names in py3. (Ales Kozumplik)
- tests: clean up the functions that load seeded comps a bit. (Ales Kozumplik)
- remove: cli._*aybeYouMeant(). (Ales Kozumplik)
- simplify groups/envs API methods in Base a lot. (Ales Kozumplik)
- tests: add test for Base._translate_comps_pkg_types() (Ales Kozumplik)
- refactor: move the group listing etc. methods() away from Base into GroupCommand. (Ales Kozumplik)
- api: add group.upgrade opration to Base and CLI (RhBug:1029022) (Ales Kozumplik)
- remove: OriginalGroupPersistor. (Ales Kozumplik)
- groups: store format version of the groups db. (Ales Kozumplik)
- groups: saving the persistent data. (Ales Kozumplik)
- refactor: extract out the transactioning part of _main(). (Ales Kozumplik)
- groups: Integrate the redone componenets with Base. (Ales Kozumplik)
- Add comps Solver. (Ales Kozumplik)
- groups: redo the GroupPersistor class. (Ales Kozumplik)
- doc: faq: why we don't check for root. (RhBug:1088166) (Ales Kozumplik)
- cosmetic: reordered import statements (Jan Silhan)
- added --refresh option (RhBug:1064226) (Jan Silhan)
- added forgotten import (Jan Silhan)
- fixed import errors after yum/i18n.py removal (Jan Silhan)
- removed to_utf8 from yum/i18n.py (Jan Silhan)
- removed to_str from yum/i18n.py (Jan Silhan)
- removed utf8_text_fill from yum/i18n.py (Jan Silhan)
- removed utf8_width from yum/i18n.py (Jan Silhan)
- removed utf8_width_fill from yum/i18n.py (Jan Silhan)
- removed to_unicode from yum/i18n.py (Jan Silhan)
- make all strings unicode_literals implicitly (Jan Silhan)
- moved _, P_ to dnf/i18n.py (Jan Silhan)
- removed utf8_valid from yum/i18n.py (Jan Silhan)
- removed str_eq from yum/i18n.py (Jan Silhan)
- removed exception2msg from yum/i18n.py (Jan Silhan)
- removed dummy_wrapper from yum/i18n.py (Jan Silhan)
- cosmetics: leave around the good things from 660c3e5 (documentation, UT). (Ales Kozumplik)
- Revert "fix: provides are not recognized for erase command. (RhBug:1087063)" (Ales Kozumplik)
- fix: provides are not recognized for erase command. (RhBug:1087063) (Ales Kozumplik)
- test: fix UsageTest test, so it work without dnf is installed on the system PEP8 cleanup (Tim Lauridsen)
- cleanup: getSummary() and getUsage() can be dropped entirely now. (Ales Kozumplik)
- test: use Command.usage & Command.summary API in unittest (Tim Lauridsen)
- show plugin commands in separate block api: add new public Command.usage & Command.summary API cleanup: make Commands (Tim Lauridsen)
- tests: move libcomps test to a separate test file. (Ales Kozumplik)
- refactor: put DistoSyncCommand into its own file (Tim Lauridsen)
- refactor: commands.group: _split_extcmd is a static method. (Ales Kozumplik)
- GroupsCommand: make the way comps are searched more robust. (RhBug:1051869) (Ales Kozumplik)
- tests: move GroupCommand tests to a more proper place. (Ales Kozumplik)
- fix leak: Base.__del__ causes GC-uncollectable circles. (Ales Kozumplik)
- gruops: 'list' and similar commands should run without root. (RhBug:1080331) (Ales Kozumplik)
- refactor: conf is given to Output on instantiation. (Ales Kozumplik)
- remove: Command.done_command_once and Command.hidden. (Ales Kozumplik)
- [doc] improve documentation of '--best' (RhBug:1084553) (Ales Kozumplik)
- api: Command.base and Command.cli are API attributes. (Ales Kozumplik)
- demands: similarly to 78661a4, commands should set the exit success_exit_status directly. (Ales Kozumplik)
- demands: commands requiring resolving dymamically need to set the demand now. (Ales Kozumplik)
- doc: typo in group doc. (RhBug:1084139) (Ales Kozumplik)
- api: Base.resolve() takes allow_erasing. (RhBug:1073859) (Ales Kozumplik)
- refactor: OptionParser._checkAbsInstallRoot is static. (Ales Kozumplik)
- option_parser: remove base dependency. (Ales Kozumplik)
- move: dnf.cli.cli.OptionParser -> dnf.cli.option_parser.OptionParser. (Ales Kozumplik)
- doc: 'clean packages' incorrectly mentions we do not delete cached packages. (RhBug:1083767) (Ales Kozumplik)
- fix: TypeError in dnf history info <id> (RHBug: #1082230) (Tim Lauridsen)
- Start new version: 0.5.0. (Ales Kozumplik)
- remove: instance attrs of Base, namely cacheonly. (Ales Kozumplik)
- tests: remove: support.MockCli. (Ales Kozumplik)
- tests: fix locale independence. (Radek Holy)
- cleanups in cli.OptionParser. (Ales Kozumplik)
- fix: PendingDeprecationWarning from RPM in gpgKeyCheck(). (Ales Kozumplik)
- api: add Cli.demands.root_user (RhBug:1062889) (Ales Kozumplik)
- api: add Cli.demands and Command.config() to the API (RhBug:1062884) (Ales Kozumplik)
- Integrate DemandSheet into CLI. (Ales Kozumplik)
- Command.configure() takes the command arguments like run(). (Ales Kozumplik)
- Add dnf.cli.demand.DemandSheet. (Ales Kozumplik)
- remove: dead code for deplist, version and check-rpmdb commands. (Ales Kozumplik)
- sync with transifex (Jan Silhan)
- removed _enc method that did nothing without specspo (Jan Silhan)
- fixed local reinstall error (Jan Silhan)
- Fix Term.MODE setting under Python 3 in case of incapable tty stdout. (Radek Holy)
- tests: move Term tests to better file. (Radek Holy)
- refactor: move ReinstallCommand in its own module. (Ales Kozumplik)
- rename: yumbase (case insensitive) -> base. (Ales Kozumplik)
- fixed py3 error thrown by search command (Jan Silhan)
- fixed wrong named variable (Jan Silhan)
- fixed local downgrade error (Jan Silhan)
- doc: fix Package references that are ambiguous now. (Ales Kozumplik)
- fix: resource leak in yum.misc.checksum() under py3. (Ales Kozumplik)
- fix: leak: couple of files objects left open. (Ales Kozumplik)
- fix PendingDepreaction warning from rpm in _getsysver(). (Ales Kozumplik)
- repo: Repo.cachedir is not a list. (Ales Kozumplik)
- api: add Base.package_install et al. and Base.add_remote_rpm(). (RhBug:1079519) (Ales Kozumplik)
- tests: fix tests broken under foreign locale after 32818b2. (Ales Kozumplik)
- refactor: move install, downgrade and upgrade commands into separate modules. (Ales Kozumplik)
- tests: refactor: make Term tests more isolated. (Radek Holy)
- tests: fix terminfo capability independence. (Radek Holy)
- api: explain that Base is a context manager with a close(). (Ales Kozumplik)
- cosmetic: move stuff around in comps. (Ales Kozumplik)
- api: groups: add comps.Package, add group.package_iter(). (RhBug:1079932) (Ales Kozumplik)
- fixed installation of conflicted packages (RhBug:1061780) (Jan Silhan)
- removed never executed code based on _ts_saved_file variable (Jan Silhan)
- added logrotate script and ownership of log files to dnf (RhBug:1064211) (Jan Silhan)
- fixed: highlight characters broken under py3 (RhBug:1076884) (Jan Silhan)
- remove: base.deselectGroup(). it is not used. (Ales Kozumplik)
- tests: fix broken InstallMultilib.test_install_src_fails(). (Ales Kozumplik)
- groups: support manipulation with environments (RhBug:1063666) (Ales Kozumplik)
- add dnf.util.partition(). (Ales Kozumplik)
- refactor: RepoPersistor: use the global logger instead of an instance variable. (Ales Kozumplik)
- groups: besides installed groups also store persistently the environments. (Ales Kozumplik)
- rename: persistor.Groups -> ClonableDict. (Ales Kozumplik)
- doc: cli_vs_yum: typography in bandwidth limiting section. (Ales Kozumplik)
- doc: cli_vs_yum: we do not partially allow operations that install .srpm. (RhBug:1080489) (Ales Kozumplik)
- refactor: imports order in cli/commands/__init__.py. (Ales Kozumplik)
- refactor: groups: make all commands use _patterns2groups(). (Ales Kozumplik)
- kernel: remove kernel-source from const.INSTALLONLYPKGS. (Ales Kozumplik)
- build: 0.4.19-1 (Ales Kozumplik)
- New version: 0.4.19 (Ales Kozumplik)
- downloads: bump number of downloaded files on a skip. (RhBug:1079621) (Ales Kozumplik)
- packaging: add dnf.cli.commands to the installation. (Ales Kozumplik)
- refactor: put GroupCommand into its separate module. (Ales Kozumplik)
- rename: make cli.commands a subpackage. (Ales Kozumplik)
- AUTHORS: added Albert. (Ales Kozumplik)
- test: fixed CacheTest.test_noroot() when running as root (Albert Uchytil)
- AUTHORS: added Tim. (Ales Kozumplik)
- fixes TypeError: '_DownloadErrors' object is not iterable (RhBug:1078832) (Tim Lauridsen)
- fixed not including .mo files (Jan Silhan)
- comps: _by_pattern() no longer does the comma splitting. (Ales Kozumplik)

* Mon Mar 24 2014 Aleš Kozumplík <ales@redhat.com> - 0.4.19-1
- downloads: bump number of downloaded files on a skip. (RhBug:1079621) (Ales Kozumplik)
- packaging: add dnf.cli.commands to the installation. (Ales Kozumplik)
- refactor: put GroupCommand into its separate module. (Ales Kozumplik)
- rename: make cli.commands a subpackage. (Ales Kozumplik)
- AUTHORS: added Albert. (Ales Kozumplik)
- test: fixed CacheTest.test_noroot() when running as root (Albert Uchytil)
- AUTHORS: added Tim. (Ales Kozumplik)
- fixes TypeError: '_DownloadErrors' object is not iterable (RhBug:1078832) (Tim Lauridsen)
- fixed not including .mo files (Jan Silhan)
- comps: _by_pattern() no longer does the comma splitting. (Ales Kozumplik)
- including .mo files correctly (Jan Silhan)
- tests: fix locale independence. (Radek Holy)
- remove: unused trashy methods in dnf.yum.misc. (Ales Kozumplik)
- persistor: do not save Groups if it didn't change (RhBug:1077173) (Ales Kozumplik)
- tests: simplify the traceback logging. (Ales Kozumplik)
- main: log IO errors etc. thrown even during Base.__exit__. (Ales Kozumplik)
- logging: do not log IOError tracebacks in verbose mode. (Ales Kozumplik)
- refactor: move out main._main()'s inner error handlers. (Ales Kozumplik)
- added gettext as a build dependency  for translation files (Jan Silhan)
- translation: updated .pot file and fetched fresh .po files from transifex (Jan Silhan)
- removed redundant word from persistor translation (Jan Silhan)
- translation: show relative path in generated pot file (Jan Silhan)
- refactor: replaced type comparisons with isinstance (Jan Silhan)
- translation: added mo files generation and including them in rpm package (Jan Silhan)
- removed unused imports in base.py (Jan Silhan)
- doc: typo in Base.group_install(). (Ales Kozumplik)

* Mon Mar 17 2014 Aleš Kozumplík <ales@redhat.com> - 0.4.18-1
- api: drop items deprecated since 0.4.9 or earlier. (Ales Kozumplik)
- api: deprecate Base.select_group() (Ales Kozumplik)
- doc: document the group marking operations. (Ales Kozumplik)
- api: add Base.group_install() with exclude capability. (Ales Kozumplik)
- groups: recognize 'mark install' instead of 'mark-install'. (Ales Kozumplik)
- Allow installing optional packages from a group. (RhBug:1067136) (Ales Kozumplik)
- groups: add installing groups the object marking style. (Ales Kozumplik)
- groups: add Base.group_remove(). (Ales Kozumplik)
- groups: add support for marking/unmarking groups. (Ales Kozumplik)
- groups: add dnf.persistor.GroupPersistor(), to store the installed groups. (Ales Kozumplik)
- logging: log plugin import tracebacks on the subdebug level. (Ales Kozumplik)
- rename: dnf.persistor.Persistor -> RepoPersistor. (Ales Kozumplik)
- doc: update README and FAQ with the unabbreviated name. (Ales Kozumplik)
- groups: fix grouplist crashes with new libcomps. (Ales Kozumplik)
- Do not terminate for unreadable repository config. (RhBug:1071212) (Ales Kozumplik)
- cli: get rid of ridiculous slashes and the file:// scheme on config read fails. (Ales Kozumplik)
- repo: log more than nothing about a remote repo MD download. (Ales Kozumplik)
- drpm: fallback to .rpm download on drpm rebuild error. (RhBug:1071501) (Ales Kozumplik)
- remove: Base.download_packages()' inner function mediasort(). (Ales Kozumplik)
- tests: tidy up the imports, in particular import mock from support. (Ales Kozumplik)
- changed documentation of distro-sync command (Jan Silhan)
- added distro-sync explicit packages support (RhBug:963710) (Jan Silhan)
- renamed testcase to distro_sync_all (Jan Silhan)
- Minor spelling (Arjun Temurnikar)
- i18n: translate repo sync error message. (Ales Kozumplik)
- add support for ppc64le (Dennis Gilmore)
- there is no arch called arm64 it is aarch64 (Dennis Gilmore)

* Wed Mar 5 2014 Aleš Kozumplík <ales@redhat.com> - 0.4.17-1
- doc: in the faq, warn users who might install rawhide packages on stable. (RhBug:1071677) (Ales Kozumplik)
- cli: better format the download errors report. (Ales Kozumplik)
- drpm: properly report applydeltarpm errors. (RhBug:1071501) (Ales Kozumplik)
- fixed Japanese translatated message (RhBug:1071455) (Jan Silhan)
- generated and synchronized translations with transifex (Jan Silhan)
- added transifex support to cmake (gettext-export, gettext-update) (Jan Silhan)
- api: expose RepoDict.get_matching() and RepoDict.all() (RhBug:1071323) (Ales Kozumplik)
- api: add Repo.set_progress_bar() to the API. (Ales Kozumplik)
- tests: test_cli_progress uses StringIO to check the output. (Ales Kozumplik)
- downloads: fix counting past 100% on mirror failures (RhBug:1070598) (Ales Kozumplik)
- repo: log callback calls to librepo. (Ales Kozumplik)
- Add repository-packages remove-or-reinstall command. (Radek Holy)
- Support negative filtering by new repository name in Base.reinstall. (Radek Holy)
- Support removal N/A packages in Base.reinstall. (Radek Holy)
- Add repository-packages remove command. (Radek Holy)
- refactor: Reduce amount of code in repository-packages subcommands. (Radek Holy)
- Support filtering by repository name in Base.remove. (Radek Holy)
- remove: BaseCli.erasePkgs (Radek Holy)
- Add repository-packages reinstall command. (Radek Holy)
- exceptions: improve empty key handling in DownloadError.__str__(). (Ales Kozumplik)
- downloads: fix fatal error message return value from download_payloads() (RhBug:1071518) (Ales Kozumplik)
- fixes problem with TypeError in Base.read_comps() in python3 (RhBug:1070710) (Tim Lauridsen)
- fix read_comps: not throwing exceptions when repo has no repodata (RhBug:1059704) (Jan Silhan)
- not decompressing groups when --cacheonly option is set (RhBug:1058224) (Jan Silhan)
- added forgotten import (Jan Silhan)
- Add repository-packages move-to command. (Radek Holy)
- Add repository-packages reinstall-old command. (Radek Holy)
- Support filtering by repository name in Base.reinstall. (Radek Holy)
- tests: test effects instead of mock calls. (Radek Holy)
- Wrap some recently added long lines. (Radek Holy)
- remove: BaseCli.reinstallPkgs (Radek Holy)
- repos: repos can never expire. (RhBug:1069538) (Ales Kozumplik)
- build: rebuild with 9d95442 (updated summaries_cache). (Ales Kozumplik)
- doc: update summaries_cache. (Ales Kozumplik)

* Wed Feb 26 2014 Aleš Kozumplík <ales@redhat.com> - 0.4.16-1
- fix: ensure MDPayload always has a valid progress attribute. (RhBug:1069996) (Ales Kozumplik)
- refactor: Move repo-pkgs upgrade-to to a standalone class instead of reusing the UpgradeToCommand. (Radek Holy)
- remove: BaseCli.updatePkgs (Radek Holy)
- refactor: Remove the reference to updatePkgs from UpgradeSubCommand. (Radek Holy)
- refactor: Remove the reference to updatePkgs from UpgradeCommand. (Radek Holy)
- refactor: Move repo-pkgs upgrade to a standalone class instead of reusing the UpgradeCommand. (Radek Holy)
- remove: BaseCli.installPkgs (Radek Holy)
- refactor: Remove the reference to installPkgs from InstallSubCommand. (Radek Holy)
- refactor: Remove the reference to installPkgs from InstallCommand. (Radek Holy)
- refactor: Move repo-pkgs install to a standalone class instead of reusing the InstallCommand. (Radek Holy)
- Revert "Support filtering by repository name in install_groupie." (Radek Holy)
- Revert "Support filtering by repository name in Base.select_group." (Radek Holy)
- Drop group filtering by repository name from installPkgs. (Radek Holy)
- Drop "repo-pkgs install @Group" support. (Radek Holy)
- refactor: Move CheckUpdateCommand.check_updates to BaseCli. (Radek Holy)
- refactor: Move repo-pkgs check-update to a standalone class instead of reusing the CheckUpdateCommand. (Radek Holy)
- refactor: Move repo-pkgs list to a standalone class instead of reusing the ListCommand. (Radek Holy)
- tests: Add tests of repo-pkgs info against the documentation. (Radek Holy)
- Fix "repo-pkgs info installed" behavior with respect to the documentation. (Radek Holy)
- refactor: Move MockBase methods to BaseStubMixin. (Radek Holy)
- refactor: Move repo-pkgs info to a standalone class instead of reusing the InfoCommand. (Radek Holy)
- refactor: Move InfoCommand._print_packages to BaseCli.output_packages. (Radek Holy)
