#!/bin/bash

set -xe

instpkgs()
{
  local i
  local PKGS

  PKGS=("$@")
  for i in ${!PKGS[@]}; do
    sudo apt-get -y install "${PKGS[i]}"
  done
}

sudo apt-get -y update

instpkgs bc bison flex git jq libc6-dev libncurses-dev libssl-dev make zip crossbuild-essential-armhf crossbuild-essential-arm64

# Ensure /tmp is large enough for pimod to decompress the base image in /tmp
# This may require a reboot to take effect
sudo mkdir -p /etc/systemd/system/tmp.mount.d

cat > /etc/systemd/system/tmp.mount.d/override.conf << EOF
[Mount]
Options=mode=1777,strictatime,nosuid,nodev,size=4G
EOF

# If this fails, a reboot is required
sudo systemctl daemon-reexec
sudo systemctl restart tmp.mount
