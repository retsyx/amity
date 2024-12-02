#!/bin/bash

# Build 64-bit v8, and 2712 Linux kernel bundles for Raspberry Pi.
# Allows specifying config edits to be applied on top of the standard kernel configs.
# Example invocation:
#
# build-kernel.sh -s amity -t 2717 -c 5aeecea -o config-overlay
# Based on the build scripts posted by RonR: https://forums.raspberrypi.com/viewtopic.php?t=343387

set -xe

JOBS=$(nproc --all)

HOME_DIR=~
ROOT_DIR=${HOME_DIR}/linux-build
CACHE_DIR=${ROOT_DIR}/cache
SRC_DIR=${ROOT_DIR}/src
LINUX_SRC_DIR=${SRC_DIR}/linux
STAGING_DIR=${ROOT_DIR}/staging
OUT_DIR=${ROOT_DIR}/out

mkdir -p ${ROOT_DIR}
mkdir -p ${CACHE_DIR}
mkdir -p ${SRC_DIR}
mkdir -p ${STAGING_DIR}
mkdir -p ${OUT_DIR}

export MAKEFLAGS=-j${JOBS} ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-

SUFFIX="rpi999"
COMMITID=""
TARGET_KERNEL=""
CONFIG_OVERLAY=""

usage()
{
  cat <<EOF

Usage: $0 [options]
-s,--suffix          Kernel build suffix
-c,--commitid        Git commitid to build
-t,--target          Target kernel to make
    v8
    2712
-o,--overlay         Configuration file to overlay
-h,--help            This usage description

EOF
}

while [ $# -gt 0 ]; do
  case "$1" in

    -s|--suffix)
      SUFFIX="$2"
      shift 2
      ;;

    -c|--commitid)
      COMMITID="$2"
      shift 2
      ;;

    -t|--target)
      TARGET_KERNEL="$2"
      shift 2
      ;;

    -o|--overlay)
      CONFIG_OVERLAY=$(readlink -f "$2")
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

case "${TARGET_KERNEL}" in

  v8)
    DEFCFG=bcm2711_defconfig
    KERNEL_IMG="kernel8.img"
    ;;

  2712)
    DEFCFG=bcm2712_defconfig
    KERNEL_IMG="kernel_2712.img"
    ;;

  *)
    echo "Invalid target"
    exit 1
    ;;

esac

if [ -d ${LINUX_SRC_DIR} ]; then
  CURRENT_COMMITID=$(cat ${LINUX_SRC_DIR}/COMMITID || echo "NO COMMITID")
  if [ "${CURRENT_COMMITID}" != "${COMMITID}" ]; then
    rm -rf ${LINUX_SRC_DIR}
  fi
fi

if [ ! -d ${LINUX_SRC_DIR} ]; then
    mkdir ${LINUX_SRC_DIR}
    CACHED_ARCHIVE=${CACHE_DIR}/${COMMITID}.tar.gz
    if [ ! -f ${CACHED_ARCHIVE} ]; then
        curl -L -o ${CACHED_ARCHIVE} https://github.com/raspberrypi/linux/archive/${COMMITID}.tar.gz
    fi
    tar xfz ${CACHED_ARCHIVE} --strip-components=1 -C ${LINUX_SRC_DIR}
    echo ${COMMITID} > ${LINUX_SRC_DIR}/COMMITID
fi

cd ${LINUX_SRC_DIR}

make ${DEFCFG}

if [ "${CONFIG_OVERLAY}" != "" ]; then
    scripts/kconfig/merge_config.sh .config ${CONFIG_OVERLAY}
fi

if [ "${SUFFIX}" != "" ]; then
  sed -i "s|^\(CONFIG_LOCALVERSION=\".*\)\"$|\1-${SUFFIX}\"|" .config
fi

BUILD_ID="$(sed -n 's|^.*\s\+\(\S\+\.\S\+\.\S\+\)\s\+Kernel Configuration$|\1|p' .config)-${SUFFIX}-rpi-${TARGET_KERNEL}"
DSTDIR="${STAGING_DIR}/kernel-${COMMITID}"
mkdir -p $DSTDIR
make KERNELRELEASE="${BUILD_ID}" Image.gz modules dtbs
make KERNELRELEASE="${BUILD_ID}" INSTALL_MOD_PATH=${DSTDIR} modules_install
mkdir -p "${DSTDIR}/boot/firmware/overlays/"
mkdir -p "${DSTDIR}/lib/linux-image-${BUILD_ID}/broadcom/"
mkdir -p "${DSTDIR}/lib/linux-image-${BUILD_ID}/overlays/"
cp .config "${DSTDIR}/boot/config-${BUILD_ID}"
echo "ffffffffffffffff B The real System.map is in the linux-image-<version>-dbg package" > "${DSTDIR}/boot/System.map-${BUILD_ID}"
cp arch/arm64/boot/Image.gz "${DSTDIR}/boot/vmlinuz-${BUILD_ID}"
cp arch/arm64/boot/dts/broadcom/*.dtb "${DSTDIR}/lib/linux-image-${BUILD_ID}/broadcom/"
cp arch/arm64/boot/dts/overlays/*.dtb* "${DSTDIR}/lib/linux-image-${BUILD_ID}/overlays/"
cp arch/arm64/boot/dts/overlays/README "${DSTDIR}/lib/linux-image-${BUILD_ID}/overlays/"
cp arch/arm64/boot/Image.gz "${DSTDIR}/boot/firmware/${KERNEL_IMG}"
cp arch/arm64/boot/dts/broadcom/*.dtb "${DSTDIR}/boot/firmware/"
cp arch/arm64/boot/dts/overlays/*.dtb* "${DSTDIR}/boot/firmware/overlays/"
cp arch/arm64/boot/dts/overlays/README "${DSTDIR}/boot/firmware/overlays/"

ARCHIVE="kernel-$(sed -n 's|^.*\s\+\(\S\+\.\S\+\.\S\+\)\s\+Kernel Configuration$|\1|p' .config)$(sed -n 's|^CONFIG_LOCALVERSION=\"\(.*\)\"$|\1|p' .config).zip"
cd "${DSTDIR}"
find lib -type l -exec rm {} \;
zip -q -r "${ARCHIVE}" *
mv "${DSTDIR}/${ARCHIVE}" "${OUT_DIR}"
rm -r "${DSTDIR}"

