Name:           systemd
Version:        219
Release:        30
License:        LGPLv2
Summary:        Fake package

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
