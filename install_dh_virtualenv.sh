#!/bin/bash
set -u -e
apt-get update
apt-get install -y devscripts python-virtualenv git equivs
git clone https://github.com/spotify/dh-virtualenv.git
/bin/echo -e 'APT::Get::Assume-Yes "true";\nAPT::Get::force-yes "true";' >/etc/apt/apt.conf.d/90forceyes
(cd dh-virtualenv && git checkout 0.10 && mk-build-deps -ri && dpkg-buildpackage -us -uc -b)
dpkg -i dh-virtualenv_*.deb
