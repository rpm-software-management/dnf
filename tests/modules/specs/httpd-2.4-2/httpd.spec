Name:           httpd
Version:        2.4.25
Release:        8
License:        LGPLv2
Summary:        Fake package

Requires:       glibc
Requires:       libnghttp2

%description
Fake package

%package doc
Summary:        Fake package

%description doc
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
%files doc
%files debuginfo


%changelog
