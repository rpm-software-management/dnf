Name:           glibc
Version:        2.25
Release:        4
License:        LGPLv2
Summary:        Fake package

Requires:       %{name}-common = %{version}-%{release}
Requires:       basesystem
%if %__isa_bits == 32
Provides:       libc.so.6()
Provides:       libpthread.so.0(GLIBC_2.0)
%else
Provides:       libc.so.6()(64bit)
Provides:       libpthread.so.0(GLIBC_2.3)(64bit)
%endif

%description
Fake package

%package common
Summary:        Fake package

%description common
Fake package

%package -n dummy-nscd
Summary:        Fake package

%description -n dummy-nscd
Fake package

%package debuginfo
Summary:        Fake package
Group:          Development/Debug

%description debuginfo
Fake package

%package debuginfo-common
Summary:        Fake package
Group:          Development/Debug

%description debuginfo-common
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
%if %__isa_bits == 32
%ghost /usr/lib/libc.so.6
%else
%ghost /usr/lib64/libc.so.6
%endif

%files common
%files -n dummy-nscd
%files debuginfo
%files debuginfo-common


%changelog
