Name: foo
Version: 1
Release: 1%{?snapshot}
Summary: a testing package
License: GPLv2+
Source: %{name}-%{version}.tar.gz

%description
A package intended to test DNF.

%files
