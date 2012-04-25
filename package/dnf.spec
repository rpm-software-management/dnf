%global gitrev 70753dd

Name:		dnf
Version:	0.2.0
Release:	2.%{gitrev}%{?dist}
Summary:	A highly experimental Yum replacement on top of libsolv.
Group:		System Environment/Base
License:	GPLv2+
URL:		https://github.com/akozumpl/dnf
Source0:	dnf-%{gitrev}.tar.xz
BuildArch:	noarch
BuildRequires:	cmake python2
Requires:	python-hawkey >= 0.2.0-3

%description
A highly experimental Yum replacement on top of libsolv.

%prep
%setup -q -n dnf

%build
%cmake .
make %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

%files
%{_bindir}/*
%{python_sitelib}/dnf/*

%changelog
* Thu Apr 25 2012 Aleš Kozumplík <akozumpl@redhat.com> - 0.2.0-2.git70753dd%{?dist}
- New version.

* Thu Apr 12 2012 Aleš Kozumplík <akozumpl@redhat.com> - 0.1-0.git833c054%{?dist}
- Initial package.
