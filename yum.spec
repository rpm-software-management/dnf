Summary: RPM installer/updater
Name: yum
Version: 3.4.2
Release: 0
License: GPLv2+
Group: System Environment/Base
Source: %{name}-%{version}.tar.gz
URL: http://yum.baseurl.org/
BuildRoot: %{_tmppath}/%{name}-%{version}root
BuildArchitectures: noarch
BuildRequires: python
BuildRequires: gettext
BuildRequires: intltool

Requires: python >= 2.4
Requires: rpm-python, rpm >= 0:4.4.2
Requires: python-sqlite
Requires: urlgrabber >= 3.9.2
Requires: yum-metadata-parser >= 1.1.0
Requires: python-iniparse
Requires: pygpgme
Conflicts: rpm >= 5-0
# Zif is a re-implementation of yum in C, however:
#
# 1. There is no co-operation/etc. with us.
# 2. It touches our private data directly.
#
# ...both of which mean that even if there were _zero_ bugs in zif, we'd
# never be able to change anything after the first user started using it. And
# of course:
#
# 3. Users will never be able to tell that it isn't weird yum bugs, when they
# hit them (and we'll probably never be able to debug them, without becoming
# zif experts).
#
# ...so we have two sane choices: i) Conflict with it. 2) Stop developing yum.
Conflicts: zif
Obsoletes: yum-skip-broken <= 1.1.18
Obsoletes: yum-basearchonly <= 1.1.9
Obsoletes: yum-allow-downgrade < 1.1.20-0
Obsoletes: yum-plugin-allow-downgrade < 1.1.22-0
Obsoletes: yum-plugin-protect-packages < 1.1.27-0
Provides: yum-skip-broken
Provides: yum-basearchonly
Provides: yum-allow-downgrade
Provides: yum-plugin-allow-downgrade
Provides: yum-protect-packages
Provides: yum-plugin-protect-packages

%description
Yum is a utility that can check for and automatically download and
install updated RPM packages. Dependencies are obtained and downloaded 
automatically, prompting the user for permission as necessary.

%package updatesd
Summary: Update notification daemon
Group: Applications/System
Requires: yum = %{version}-%{release}
Requires: dbus-python
Requires: pygobject2
Requires(preun): /sbin/chkconfig 
Requires(preun): /sbin/service
Requires(postun): /sbin/chkconfig 
Requires(postun): /sbin/service


%description updatesd
yum-updatesd provides a daemon which checks for available updates and 
can notify you when they are available via email, syslog or dbus. 


%package cron
Summary: Files needed to run yum updates as a cron job
Group: System Environment/Base
Requires: yum >= 3.0 vixie-cron crontabs yum-plugin-downloadonly findutils
Requires(post): /sbin/chkconfig
Requires(post): /sbin/service
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
Requires(postun): /sbin/service

%description cron
These are the files needed to run yum updates as a cron job.
Install this package if you want auto yum updates nightly via cron.

%prep
%setup -q

%build
make


%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install
# install -m 644 %{SOURCE1} $RPM_BUILD_ROOT/etc/yum/yum.conf
# install -m 755 %{SOURCE2} $RPM_BUILD_ROOT/etc/cron.daily/yum.cron

# Ghost files:
mkdir -p $RPM_BUILD_ROOT/var/lib/yum/history
mkdir -p $RPM_BUILD_ROOT/var/lib/yum/plugins
mkdir -p $RPM_BUILD_ROOT/var/lib/yum/yumdb
touch $RPM_BUILD_ROOT/var/lib/yum/uuid

%find_lang %name

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


%post cron
# Make sure chkconfig knows about the service
/sbin/chkconfig --add yum-cron
# if an upgrade:
if [ "$1" -ge "1" ]; then
# if there's a /etc/rc.d/init.d/yum file left, assume that there was an
# older instance of yum-cron which used this naming convention.  Clean 
# it up, do a conditional restart
 if [ -f /etc/init.d/yum ]; then 
# was it on?
  /sbin/chkconfig yum
  RETVAL=$?
  if [ $RETVAL = 0 ]; then
# if it was, stop it, then turn on new yum-cron
   /sbin/service yum stop 1> /dev/null 2>&1
   /sbin/service yum-cron start 1> /dev/null 2>&1
   /sbin/chkconfig yum-cron on
  fi
# remove it from the service list
  /sbin/chkconfig --del yum
 fi
fi 
exit 0

%preun cron
# if this will be a complete removeal of yum-cron rather than an upgrade,
# remove the service from chkconfig control
if [ $1 = 0 ]; then
 /sbin/chkconfig --del yum-cron
 /sbin/service yum-cron stop 1> /dev/null 2>&1
fi
exit 0

%postun cron
# If there's a yum-cron package left after uninstalling one, do a
# conditional restart of the service
if [ "$1" -ge "1" ]; then
 /sbin/service yum-cron condrestart 1> /dev/null 2>&1
fi
exit 0



%files -f %{name}.lang
%defattr(-, root, root)
%doc README AUTHORS COPYING TODO INSTALL ChangeLog PLUGINS
%config(noreplace) %{_sysconfdir}/yum/yum.conf
%config(noreplace) %{_sysconfdir}/yum/version-groups.conf
%dir %{_sysconfdir}/yum
%dir %{_sysconfdir}/yum/protected.d
%dir %{_sysconfdir}/yum/repos.d
%dir %{_sysconfdir}/yum/vars
%config %{_sysconfdir}/logrotate.d/%{name}
%{_sysconfdir}/bash_completion.d
%{_datadir}/yum-cli/*
%exclude %{_datadir}/yum-cli/yumupd.py*
%{_bindir}/yum
/usr/lib/python?.?/site-packages/yum
/usr/lib/python?.?/site-packages/rpmUtils
%dir /var/cache/yum
%dir /var/lib/yum
%ghost /var/lib/yum/uuid
%ghost /var/lib/yum/history
%ghost /var/lib/yum/plugins
%ghost /var/lib/yum/yumdb
%{_mandir}/man*/yum.*
%{_mandir}/man*/yum-shell*


%files cron
%defattr(-,root,root)
%doc COPYING
%{_sysconfdir}/cron.daily/0yum.cron
%config(noreplace) %{_sysconfdir}/yum/yum-daily.yum
%config(noreplace) %{_sysconfdir}/yum/yum-weekly.yum
%{_sysconfdir}/rc.d/init.d/yum-cron
%config(noreplace) %{_sysconfdir}/sysconfig/yum-cron




%files updatesd
%defattr(-, root, root)
%config(noreplace) %{_sysconfdir}/yum/yum-updatesd.conf
%config %{_sysconfdir}/rc.d/init.d/yum-updatesd
%config %{_sysconfdir}/dbus-1/system.d/yum-updatesd.conf
%{_datadir}/yum-cli/yumupd.py*
%{_sbindir}/yum-updatesd
%{_mandir}/man*/yum-updatesd*

%changelog
* Wed Apr 20 2011 James Antill <james at fedoraproject.org>
- 3.4.1
- umask bug fix.

* Thu Apr 14 2011 James Antill <james at fedoraproject.org>
- 3.4.0

* Wed Jan 12 2011 Seth Vidal <skvidal at fedoraproject.org>
- put yum-cron back into yum and make the subpkg. Thanks To Alec Habig for
  maintaining this so well for so long.

* Fri Jul 30 2010 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.28

* Thu Mar 18 2010 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.27

* Tue Feb  9 2010 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.26

* Tue Oct 13 2009 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.25

* Thu Sep  3 2009 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.24

* Tue May 19 2009 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.23

* Tue Mar 24 2009 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.22

* Wed Jan  7 2009 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.21

* Mon Oct 27 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.20

* Mon Aug 25 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.19

* Thu Aug  7 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.18

* Wed Jul  8 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.17 

* Wed May 14 2008 Seth Vidal <skvidal at fedoraproject.org>
-  3.2.16

* Wed May 14 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.15

* Mon Apr  7 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.14

* Thu Mar 20 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.13

* Mon Mar  3 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.12

* Fri Feb  8 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.11
* Sun Jan 27 2008 James Bowes <jbowes@redhat.com>
- Move the yumupd module to yum-updatesd

* Sat Jan 26 2008 Tim Lauridsen <timlau at fedoraproject.org>
- Added BuildRequires: intltool
- Added -f %%{name}.lang to %%files
- Added %%find_lang %%name to %%install
* Thu Jan 24 2008 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.10

* Thu Jan 24 2008 Seth Vidal <skvidal at fedoraproject.org>
- wee 3.2.9

* Wed Dec 12 2007 Seth Vidal <skvidal at fedoraproject.org>
- add pygpgme dep for new gpg key handling

* Mon Dec  3 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.8

* Fri Oct 12 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.7

* Fri Oct  5 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.6

* Mon Sep 10 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.5

* Tue Aug 28 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.4
- add python-iniparse - it's a dep here but yum will run w/o it

* Fri Jul 20 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.2

* Thu Jun 21 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.1

* Wed May 16 2007 Seth Vidal <skvidal at fedoraproject.org>
- 3.2.0

* Thu Apr 26 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.7

* Tue Apr  3 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.6

* Wed Mar 21 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.5

* Wed Mar  7 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.4

* Thu Mar  1 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.3

* Wed Feb 14 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.2

* Tue Feb  6 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.1

* Sun Jan 21 2007 Seth Vidal <skvidal at linux.duke.edu>
- 3.1.0 

* Wed Oct  4 2006 Seth Vidal <skvidal at linux.duke.edu>
- 3.0

* Fri Sep 29 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.8

* Tue Sep 26 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.7

* Wed Sep  6 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.6

* Mon Aug 21 2006 Seth Vidal <skvidal at linux.duke.edu>
- 2.9.5

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
