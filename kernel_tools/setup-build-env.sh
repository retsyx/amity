#!/bin/bash

set -xe

instpkgs()
{
  local i
  local PKGS

  PKGS=("$@")
  for i in ${!PKGS[@]}; do
    sudo apt -y install "${PKGS[i]}"
  done
}

sudo apt -y update

instpkgs bc bison flex git libc6-dev libncurses-dev libssl-dev make zip crossbuild-essential-armhf crossbuild-essential-arm64
