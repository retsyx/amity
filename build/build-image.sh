#!/bin/bash

set -xe

COMPILE_KERNEL=YES
VERSION=v999.999.999

usage()
{
  cat <<EOF

Usage: $0 [options]
-v,--version         Release version (presently only used for amity-os.json)
-n,--nokernel        Skip compiling the kernel
-h,--help            This usage description

EOF
}

while [ $# -gt 0 ]; do
  case "$1" in

    -n|--nokernel)
      COMPILE_KERNEL=NO
      shift 1
      ;;

    -v|--version)
      VERSION="$2"
      shift 2
      ;;

    -h|--help)
      usage
      exit
      ;;

    -*|--*)
      echo "Unrecognized option"
      exit
      ;;

  esac
done


mkdir -p ~/amity-build

# Build GPIO enabled Linux kernels
if [ "$COMPILE_KERNEL" = "YES" ]; then
    COMMITID=$(cat kernel-commitid)
    EXTERNAL_CMD=$(readlink -f ./module_tools/build-lg-magic.sh)
    ./kernel_tools/build-kernel.sh -s amity -t v8 -c $COMMITID -o kernel-config-overlay -x ${EXTERNAL_CMD}
    ./kernel_tools/build-kernel.sh -s amity -t 2712 -c $COMMITID -o kernel-config-overlay -x ${EXTERNAL_CMD}
fi

pushd ../..
tar --exclude='*/.vscode' --exclude='*/__pycache__' --exclude='*/.DS_Store' -czf ~/amity-build/amity.tar.gz amity
popd

cp amity.Pifile ~/amity-build/.

pushd ~/amity-build

sudo ~/pimod/pimod.sh amity.Pifile

# Mount the image as a loopback device and zero free blocks to improve compressed image size
LOOP_DEVICE=$(sudo losetup -fP --show amity.img)
sudo zerofree ${LOOP_DEVICE}p2
sudo losetup -d ${LOOP_DEVICE}

# All systems define UID?
if [ "$UID" = "" ]; then
    UID=$(id -u)
fi

# Some systems define GID, and some don't?
if [ "$GID" = "" ]; then
    GID=$(id -g)
fi

RELEASE_DATE=$(date +"%Y-%m-%d")
EXTRACT_SIZE=$(stat -c %s amity.img)
EXTRACT_HASH=$(sha256sum amity.img | awk '{print $1}')

sudo chown $UID:$GID amity.img

xz --force amity.img

DOWNLOAD_SIZE=$(stat -c %s amity.img.xz)
DOWNLOAD_HASH=$(sha256sum amity.img.xz | awk '{print $1}')

jq -n \
  --arg VERSION "$VERSION" \
  --arg RELEASE_DATE "$RELEASE_DATE" \
  --argjson EXTRACT_SIZE "$EXTRACT_SIZE" \
  --arg EXTRACT_HASH "$EXTRACT_HASH" \
  --argjson DOWNLOAD_SIZE "$DOWNLOAD_SIZE" \
  --arg DOWNLOAD_HASH "$DOWNLOAD_HASH" \
'{
  "os_list": [
    {
      "name": "Amity",
      "description": "HDMI-CEC Home Theater Control",
      "url": "https://github.com/retsyx/amity/releases/download/\($VERSION)/amity.img.xz",
      "icon": "https://github.com/retsyx/amity/releases/download/\($VERSION)/icon.png",
      "website": "https://github.com/retsyx/amity",
      "release_date": $RELEASE_DATE,
      "extract_size": $EXTRACT_SIZE,
      "extract_sha256": $EXTRACT_HASH,
      "image_download_size": $DOWNLOAD_SIZE,
      "image_download_sha256": $DOWNLOAD_HASH,
      "devices": [
        "pi3-64bit",
        "pi4-64bit",
        "pi5-64bit"
      ],
      "init_format": "cloudinit-rpi",
      "architecture": "arm64",
      "capabilities": []
    }
 ]
}' > amity-os.json

popd