Name:           bash
Version:        4.2.46
Release:        21
License:        LGPLv2
Summary:        Fake package

Requires:       glibc
%if %__isa_bits == 32
Requires:       libpthread.so.0(GLIBC_2.0)
%else
Requires:       libpthread.so.0(GLIBC_2.3)(64bit)
%endif

%description
Fake package

%package debuginfo
Summary:        Fake package
Group:          Development/Debug

%description debuginfo
Fake package


%package doc
Summary:        Fake package
BuildArch:      noarch
Requires:       %{name}

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
