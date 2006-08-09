Summary: RPM installer/updater
Name: yum
Version: 2.9.4
Release: 1
License: GPL
Group: System Environment/Base
Source: %{name}-%{version}.tar.gz
URL: http://linux.duke.edu/yum/
BuildRoot: %{_tmppath}/%{name}-%{version}root
BuildArchitectures: noarch
BuildRequires: python
BuildRequires: gettext
Requires: python, rpm-python, rpm >= 0:4.1.1
Requires: python-sqlite
Requires: urlgrabber
Requires: python-elementtree
Prereq: /sbin/chkconfig, /sbin/service, coreutils


%description
Yum is a utility that can check for and automatically download and
install updated RPM packages. Dependencies are obtained and downloaded 
automatically prompting the user as necessary.

%package updatesd
Summary: Update notification daemon
Group: Applications/System
Requires: yum = %{version}-%{release}
Requires: dbus-python
Requires: pygobject2
Prereq: /sbin/chkconfig 
Prereq: /sbin/service

%description updatesd
yum-updatesd provides a daemon which checks for available updates and 
can notify you when they are available via email, syslog or dbus. 

%prep
%setup -q

%build
make


%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install
# install -m 644 %{SOURCE1} $RPM_BUILD_ROOT/etc/yum.conf
# install -m 755 %{SOURCE2} $RPM_BUILD_ROOT/etc/cron.daily/yum.cron

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT


%post updatesd
/sbin/chkconfig --add yum-updatesd
/sbin/service yum-updatesd condrestart >/dev/null 2>&1
exit 0

%preun updatesd
if [ $1 = 0 ]; then
 /sbin/chkconfig --del yum-updatesd
 /sbin/service yum-updatesd stop >/dev/null 2>&1
fi
exit 0

%files
%defattr(-, root, root)
%doc README AUTHORS COPYING TODO INSTALL ChangeLog PLUGINS
%config(noreplace) %{_sysconfdir}/yum.conf
%dir %{_sysconfdir}/yum.repos.d
%dir %{_sysconfdir}/%{name}
%config %{_sysconfdir}/logrotate.d/%{name}
%{_datadir}/yum-cli/*
%{_bindir}/yum
/usr/lib/python?.?/site-packages/yum
/usr/lib/python?.?/site-packages/rpmUtils
%dir /var/cache/yum
%{_mandir}/man*/yum.*
%{_mandir}/man*/yum-shell*

%files updatesd
%defattr(-, root, root)
%config(noreplace) %{_sysconfdir}/yum/yum-updatesd.conf
%config %{_sysconfdir}/rc.d/init.d/yum-updatesd
%config %{_sysconfdir}/dbus-1/system.d/yum-updatesd.conf
%{_sbindir}/yum-updatesd
%{_mandir}/man*/yum-updatesd*

%changelog
* Wed Aug  9 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.4

* Wed Jul 12 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.3

* Tue Jun 27 2006 Jeremy Katz <katzj@redhat.com> 
- add bits for yum-updatesd subpackage

* Tue Jun 27 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.2

* Wed Jun 21 2006 Seth Vidal <skvidal at linux.duke.edu>
- remove libxml2 dep

* Sun Jun 18 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.1

* Tue Mar  7 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.0 - new dev cycle

* Mon Mar  6 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.6.0

* Wed Feb 22 2006 Seth Vidal <skvidal@phy.duke.edu>
- 2.5.3

* Sun Jan  8 2006 Seth Vidal <skvidal@phy.duke.edu>
- 2.5.1

* Sun Aug 14 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.5.0

* Fri Aug  5 2005 Seth Vidal <skvidal@phy.duke.edu>
- back to libxml2-python req

* Fri Jul  8 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.3.4

* Tue Jun 14 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.3.3

* Wed Apr  6 2005 Seth Vidal <skvidal@phy.duke.edu>
- added python-elementtree dep, remove libxml2 dep

* Mon Apr  4 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.3.2

* Mon Mar 28 2005 Seth Vidal <skvidal@phy.duke.edu>
- add in the /etc/yum/*.yum yum shell files

* Mon Mar  7 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.3.1
- get rid of old obsoletes

* Fri Feb 25 2005 Gijs Hollestelle <gijs@gewis.nl>
- Require python-sqlite

* Fri Feb 25 2005 Seth Vidal <skvidal@phy.duke.edu>
- add yum.cron to weekly to clean packages

* Mon Feb 21 2005 Seth Vidal <skvidal@phy.duke.edu>
- new devel branch - 2.3.0

* Tue Jan 25 2005 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.13

* Sat Nov 27 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.12

* Wed Oct 27 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.11


* Tue Oct 19 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.10

* Mon Oct 18 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.9 - paper bag release


* Mon Oct 18 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.8


* Wed Oct 13 2004 Seth Vidal <skvidal@phy.duke.edu>
- update to 2.1.7
- re-include yum-arch w/deprecation notice

* Wed Oct  6 2004 Seth Vidal <skvidal@phy.duke.edu>
- mdcaching code and list changes
- 2.1.6

* Mon Oct  4 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.5

- lots of minor bugfixes and corrections


* Tue Sep 28 2004 Seth Vidal <skvidal@phy.duke.edu>
- 2.1.4

* Fri Sep  3 2004 Seth Vidal <skvidal@phy.duke.edu>
- big depsolver update

* Wed Sep  1 2004 Seth Vidal <skvidal@phy.duke.edu>
- more changes

* Tue Aug 31 2004 Seth Vidal <skvidal@phy.duke.edu>
- all new stuff for 2.1.X

* Mon Sep  8 2003 Seth Vidal <skvidal@phy.duke.edu>
- brown paper-bag 2.0.3

* Sun Sep  7 2003 Seth Vidal <skvidal@phy.duke.edu>
- bump to 2.0.2

* Fri Aug 15 2003 Seth Vidal <skvidal@phy.duke.edu>
- bump to 2.0.1

* Sun Jul 13 2003 Seth Vidal <skvidal@phy.duke.edu>
- bump to 2.0

* Sat Jul 12 2003 Seth Vidal <skvidal@phy.duke.edu>
- made yum.cron config(noreplace)

* Sat Jun  7 2003 Seth Vidal <skvidal@phy.duke.edu>
- add stubs to spec file for rebuilding easily with custom yum.conf and
- yum.cron files

* Sat May 31 2003 Seth Vidal <skvidal@phy.duke.edu>
- bump to 1.98

* Mon Apr 21 2003 Seth Vidal <skvidal@phy.duke.edu>
- bump to 1.97

* Wed Apr 16 2003 Seth Vidal <skvidal@phy.duke.edu>
- moved to fhs compliance
- ver to 1.96

* Mon Apr  7 2003 Seth Vidal <skvidal@phy.duke.edu>
- updated for 1.95 betaish release
- remove /sbin legacy
- no longer starts up by default
- do the find_lang thing

* Sun Dec 22 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped ver to 0.9.4
- new spec file for rhl 8.0

* Sun Oct 20 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped ver to 0.9.3

* Mon Aug 26 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped ver to 0.9.2

* Thu Jul 11 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped ver to 0.9.1

* Thu Jul 11 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped ver  to 0.9.0

* Thu Jul 11 2002 Seth Vidal <skvidal@phy.duke.edu>
- added rpm require

* Sun Jun 30 2002 Seth Vidal <skvidal@phy.duke.edu>
- 0.8.9

* Fri Jun 14 2002 Seth Vidal <skvidal@phy.duke.edu>
- 0.8.7

* Thu Jun 13 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped to 0.8.5

* Thu Jun 13 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped to 0.8.4

* Sun Jun  9 2002 Seth Vidal <skvidal@phy.duke.edu>
- bumped to 0.8.2
* Thu Jun  6 2002 Seth Vidal <skvidal@phy.duke.edu>
- First packaging
