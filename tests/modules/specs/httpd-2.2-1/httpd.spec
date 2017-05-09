Name:           httpd
Version:        2.2.15
Release:        59
License:        LGPLv2
Summary:        Fake package

Requires:       glibc

%description
Fake package

%package debuginfo
Summary:        Fake package
Group:          Development/Debug

%description debuginfo
Fake package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files
%files debuginfo


%changelog
