Summary: RPM installer/updater
Name: yum
Version: 0.8.9
Release: 1
License: GPL
Group: System Environment/Base
Source: %{name}-%{version}.tar.gz
#Source2: yum.conf
URL: http://www.dulug.duke.edu/yum/
BuildRoot: %{_tmppath}/%{name}-%{version}root
BuildArchitectures: noarch
BuildRequires: rpm-python python >= 1.5.2
Requires: rpm-python >= 4.0.2 perl python >= 1.5.2 
Prereq: /sbin/chkconfig, /sbin/service

%description
Yum is a utility that can check for and automatically download and
install updated RPM packages. Dependencies are obtained and downloaded 
automatically prompting the user as necessary.

%prep
%setup -q

%build
%configure 
make


%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install

#install -m 644 %{SOURCE2} $RPM_BUILD_ROOT/%{_sysconfdir}/yum.conf

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT


%post
/sbin/chkconfig --add yum
/sbin/chkconfig yum on
/sbin/service yum condrestart >> /dev/null
exit 0


%preun
if [ $1 = 0 ]; then
 /sbin/chkconfig --del yum
 /sbin/service yum stop >> /dev/null
fi
exit 0




%files 
%defattr(-, root, root)
%doc README AUTHORS COPYING TODO INSTALL
%config(noreplace) %{_sysconfdir}/yum.conf
%config %{_sysconfdir}/cron.daily/yum.cron
%config %{_sysconfdir}/init.d/%{name}
%config %{_sysconfdir}/logrotate.d/%{name}
%{_libdir}/yum/*
%{_sbindir}/yum
%{_sbindir}/yum-arch
/var/cache/yum
%{_mandir}/man*/*

%changelog
* Wed Jun 19 2002 Seth Vidal <skvidal@phy.duke.edu>
- 0.8.9

* Sun Jun 16 2002 Seth Vidal <skvidal@phy.duke.edu>
- 0.8.8

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
