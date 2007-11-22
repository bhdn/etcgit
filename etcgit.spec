%define name etcgit
%define version 0.09
%define release 1

Summary: Small cron task to keep track of the changes in /etc
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: GPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Packager: Bogdano Arendartchuk <debogdano@gmail.com>

%description
This stupid scripts will try to keep track of the changes using GIT.

It also makes separated changesets for each (RPM) package that owns the
changed files.


%prep
%setup

%build
python setup.py build

%install
python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%post
if [ ! -d /etc/.git ]; then
  cd /etc/
  git-init-db
  chmod 700 .git
  echo "created git database"
fi;

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
