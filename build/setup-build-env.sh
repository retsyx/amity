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

./kernel_tools/setup-build-env.sh

instpkgs binfmt-support fdisk file kpartx lsof p7zip-full qemu-user-static unzip wget
instpkgs xz-utils units

pushd ~
if [ ! -d "pimod" ]; then
    git clone https://github.com/Nature40/pimod
fi
popd
