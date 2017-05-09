Name:           kernel
Version:        3.10.0
Release:        514
License:        LGPLv2
Summary:        Fake package

%description
Fake package

%package headers
Summary:        Fake package

%description headers
Fake package

%package doc
Summary:        Fake package
BuildArch:      noarch

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
%files headers
%files doc


%changelog
