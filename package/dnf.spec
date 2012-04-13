%global gitrev 45d2b4a

Name:		dnf
Version:	0.1
Release:	0.%{gitrev}%{?dist}
Summary:	A highly experimental Yum replacement on top of libsolv.
Group:		System Environment/Base
License:	GPLv2+
URL:		https://github.com/akozumpl/dnf
Source0:	dnf-%{gitrev}.tar.xz
BuildArch:	noarch
BuildRequires:	cmake python2
Requires:	hawkey

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
* Thu Apr 12 2012 Aleš Kozumplík <akozumpl@redhat.com> - 0.1-0.git45d2b4a%{?dist}
- Initial package.
