Name:           grub2
Version:        2.02
Release:        0.40
License:        LGPLv2
Summary:        Fake package

Requires:       filesystem

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
