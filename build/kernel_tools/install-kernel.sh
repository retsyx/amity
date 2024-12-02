#!/bin/bash

set -xe

if [ $(id -u) -ne 0 ]; then
  echo "Must be run as root user: sudo $0"
  exit 1
fi

ARCHIVE="$1"

if [ "${ARCHIVE}" = "" ]; then
  echo "Specify archive to install"
  exit
fi

BUILD="$(unzip -l ${ARCHIVE} boot/vmlinuz-* | sed -n 's|^.*boot/vmlinuz-\(.*\)$|\1|p')"
unzip -o "${ARCHIVE}" -d /
update-initramfs -c -v -k "${BUILD}"
