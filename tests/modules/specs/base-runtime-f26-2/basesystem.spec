Name:           basesystem
Version:        11
Release:        3
License:        LGPLv2
Summary:        Fake package

Requires:       filesystem

BuildArch:      noarch

%description
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


%changelog
