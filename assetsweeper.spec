%define name gnm-assetsweeper
%define version 3.0
%define unmangled_version 3.0
%define release 17

Summary: Asset Sweeper suite
Name: %{name}
Version: %{version}
Release: %{release}
License: Internal GNM software
Source0: gnm-assetsweeper-3.0.tar.gz
Group: Applications/Productivity
#BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildRoot: ${_tmppath}/assetsweeper
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Andy Gallagher <andy.gallagher@theguardian.com>
Requires: python-psycopg2 perl-suidperl

%description
Suite of five scripts that ingests media into Vidispine in a controlled and manageable way

%prep
%setup -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/

%post
#insert commands to run post-install here

%preun
