%define name gnm-assetsweeper
%define version 3.0
%define unmangled_version 3.0
%define release dev

Summary: Asset Sweeper suite
Name: %{name}
Version: %{version}
Release: %{release}
License: Internal GNM software
Source0: assetsweeper.tar.gz
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

%build

%install
mkdir -p $RPM_BUILD_ROOT
cd $RPM_BUILD_ROOT
tar xvzf ${HOME}/rpmbuild/assetsweeper.tar.gz
rm -rf $RPM_BUILD_ROOT/home

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/

%post
#insert commands to run post-install here

%preun
