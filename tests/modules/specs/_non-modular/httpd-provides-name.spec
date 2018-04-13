Name:           httpd-provides-name
Version:        3.0
Release:        1
License:        LGPLv2
Summary:        Fake package

Requires:       glibc

Provides:       httpd

%description
Fake package

%package debuginfo
Summary:        Fake package
Group:          Development/Debug

%description debuginfo
Fake package


%package doc
Summary:        Fake package

%description doc
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
%files doc


%changelog
