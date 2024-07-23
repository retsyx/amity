#!/bin/bash

# Written by RonR: https://forums.raspberrypi.com/viewtopic.php?t=343387

trap '{ stty sane; echo ""; errexit "Aborted"; }' SIGINT SIGTERM

CONFIG1="Raspberry Pi 1, Zero and Zero W, and Raspberry Pi Compute Module 1 (32-bit) [kernel.img]"
CONFIG2="Raspberry Pi 2, 3, 3+ and Zero 2 W, and Raspberry Pi Compute Modules 3 and 3+ (32-bit) [kernel7.img]"
CONFIG3="Raspberry Pi 4 and 400, and Raspberry Pi Compute Module 4 (32-bit) [kernel7l.img]"
CONFIG4="Raspberry Pi 3, 3+, 4, 400 and Zero 2 W, and Raspberry Pi Compute Modules 3, 3+ and 4 (64-bit) [kernel8.img]"
CONFIG5="Raspberry Pi 5 (64-bit) [kernel_2712.img]"

errexit()
{
  echo ""
  echo "$1"
  echo ""
  if [ "${SRCDIR}" != "" ]; then
    rm -r "${SRCDIR}" &> /dev/null
  fi
  if [ "${DSTDIR}" != "" ]; then
    rm -r "${DSTDIR}" &> /dev/null
  fi
  exit 1
}

instpkgs()
{
  local i
  local PKGS

  PKGS=("$@")
  for i in ${!PKGS[@]}; do
    dpkg -s "${PKGS[i]}" &> /dev/null
    if [ $? -eq 0 ]; then
      unset PKGS[i]
    fi
  done
  if [ ${#PKGS[@]} -ne 0 ]; then
    echo ""
    echo -n "Ok to install ${PKGS[@]} (y/n)? "
    while read -r -n 1 -s answer; do
      if [[ ${answer} = [yYnN] ]]; then
        echo "${answer}"
        if [[ ${answer} = [nN] ]]; then
          errexit "Aborted"
        fi
        break
      fi
    done
    echo ""
    apt-get -y update
    apt-get -y install "${PKGS[@]}"
  fi
}

dispyn()
{
  local PROMPT
  local VALUE

  PROMPT=$1
  VALUE=$2
  echo -n "${PROMPT}: "
  if [ "${VALUE}" = "TRUE" ]; then
    echo "yes"
  else
    echo "no"
  fi
}

usage()
{
  cat <<EOF

Usage: $0 [options] [output directory]
-b,--branch          Branch to use (commitid/current/default/rpi-M.N.y)
-c,--config          Configuration to build:
   1 = ${CONFIG1}
   2 = ${CONFIG2}
   3 = ${CONFIG3}
   4 = ${CONFIG4}
   5 = ${CONFIG5}
-d,--delete          Delete existing source files
-f,--freshen         Freshen existing source files
-h,--help            This usage description
-i,--interactive     Interactive shell before compile
-j,--jobs            Number of jobs to run
-k,--keep            Keep old kernel as .bak
-m,--menuconfig      Run menuconfig
-n,--noinitramfs     Disable running update-initramfs
-o,--oldbootmnt      Use old boot mount (/boot)
-p,--purge           Purge source files upon completion
-r,--reboot          Reboot upon completion
-s,--suffix          Append modules suffix (suffix)
-u,--unattended      Unattended operation, defaults:
   Branch = current
   Config = ${CONFIG4}
   Delete = auto
   Freshen = no
   Interactive = no
   Jobs = 4
   Keep = no
   Menuconfig = no
   Noinitramfs = no
   Oldbootmnt = no
   Purge = no
   Reboot = no
   Suffix = none
   Xcompile = no
-x,--cross-compile   Cross-compile mode

EOF
}

olddtb()
{
  if [[ $(sed -n 's|^.*\s\+\(\S\+\)\.\S\+\.\S\+\s\+Kernel Configuration$|\1|p' .config) -lt 6 ||\
   ($(sed -n 's|^.*\s\+\(\S\+\)\.\S\+\.\S\+\s\+Kernel Configuration$|\1|p' .config) -eq 6 &&\
   $(sed -n 's|^.*\s\+\S\+\.\(\S\+\)\.\S\+\s\+Kernel Configuration$|\1|p' .config) -lt 5) ]]; then
    echo "TRUE"
  else
    echo "FALSE"
  fi
}

SRCDIR=""
DSTDIR=""
if [ $(id -u) -ne 0 ]; then
  errexit "Must be run as root user: sudo $0"
fi
PGMNAME="$(basename $0)"
for PID in $(pidof -x -o %PPID "${PGMNAME}"); do
  if [ ${PID} -ne $$ ]; then
    errexit "${PGMNAME} is already running"
  fi
done
CURDIR="$(pwd)"
if [ "${SUDO_USER}" != "" ]; then
  REALUSER="${SUDO_USER}"
else
  REALUSER="$(whoami)"
fi
RASPI=FALSE
if [[ -e /proc/device-tree/model && "$(tr -d '\0' < /proc/device-tree/model)" =~ ^Raspberry\ Pi.*$ ]]; then
  RASPI=TRUE
fi
ARCH_K="$(uname -m)"
ARCH_U="$(dpkg --print-architecture)"
OUTDIR=""
BRANCH=""
CONFIG=""
DELETE=FALSE
FRESHEN=FALSE
INTERACTIVE=FALSE
JOBS=""
KEEP=FALSE
MNUCFG=FALSE
NOINITRAMFS=FALSE
OLDBOOT=FALSE
PURGE=FALSE
REBOOT=FALSE
SUFFIX=""
UNATND=FALSE
XCOMPILE=FALSE
while [ $# -gt 0 ]; do
  case "$1" in

    -b|--branch)
      BRANCH="$2"
      shift 2
      ;;

    -c|--config)
      CONFIG="$2"
      shift 2
      ;;

    -d|--delete)
      DELETE=TRUE
      shift
      ;;

    -f|--freshen)
      FRESHEN=TRUE
      shift
      ;;

    -h|--help)
      usage
      exit
      ;;

    -i|--interactive)
      INTERACTIVE=TRUE
      shift
      ;;

    -j|--jobs)
      JOBS="$2"
      shift 2
      ;;

    -k|--keep)
      KEEP=TRUE
      shift
      ;;

    -m|--menuconfig)
      MNUCFG=TRUE
      shift
      ;;

    -n|--noinitramfs)
      NOINITRAMFS=TRUE
      shift
      ;;

    -o|--oldbootmnt)
      OLDBOOT=TRUE
      shift
      ;;

    -p|--purge)
      PURGE=TRUE
      shift
      ;;

    -r|--reboot)
      REBOOT=TRUE
      shift
      ;;

    -s|--suffix)
      SUFFIX="$2"
      shift 2
      ;;

    -u|--unattended)
      UNATND=TRUE
      shift
      ;;

    -x|--cross-compile)
      XCOMPILE=TRUE
      shift
      ;;

    -*|--*)
      errexit "Unrecognized option"
      ;;

    *)
      OUTDIR="$1"
      OUTDIR="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${OUTDIR}")"
      shift
      ;;

  esac
done
if [[ "${UNATND}" = "FALSE" && "${XCOMPILE}" = "FALSE" ]]; then
  echo ""
  echo -n "Cross-compile mode (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        XCOMPILE=TRUE
      fi
      break
    fi
  done
fi
if [[ "${XCOMPILE}" = "FALSE" && "${RASPI}" = "FALSE" ]]; then
    errexit "Local builds require a Raspberry Pi"
fi
if [[ "${UNATND}" = "FALSE" && "${CONFIG}" = "" ]]; then
  echo ""
  echo -e -n "\
1) ${CONFIG1}\n\
2) ${CONFIG2}\n\
3) ${CONFIG3}\n\
4) ${CONFIG4}\n\
5) ${CONFIG5}\n\
Configuration: "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [12345] ]]; then
      echo "${answer}"
      CONFIG="${answer}"
      break
    fi
  done
fi
if [ "${CONFIG}" = "" ]; then
  CONFIG=4
fi
case "${CONFIG}" in

  1)
    if [ "${XCOMPILE}" = "TRUE" ]; then
      MAKCFG="ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- bcmrpi_defconfig"
    else
      MAKCFG=bcmrpi_defconfig
    fi
    KRNLID="v6"
    OLDIMG="kernel.img"
    ;;

  2)
    if [ "${XCOMPILE}" = "TRUE" ]; then
      MAKCFG="ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- bcm2709_defconfig"
    else
      MAKCFG=bcm2709_defconfig
    fi
    KRNLID="v7"
    OLDIMG="kernel7.img"
    ;;

  3)
    if [ "${XCOMPILE}" = "TRUE" ]; then
      MAKCFG="ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- bcm2711_defconfig"
    else
      MAKCFG=bcm2711_defconfig
    fi
    KRNLID="v7l"
    OLDIMG="kernel7l.img"
    ;;

  4)
    if [ "${XCOMPILE}" = "TRUE" ]; then
      MAKCFG="ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- bcm2711_defconfig"
    else
      MAKCFG=bcm2711_defconfig
    fi
    KRNLID="v8"
    OLDIMG="kernel8.img"
    ;;

  5)
    if [ "${XCOMPILE}" = "TRUE" ]; then
      MAKCFG="ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- bcm2712_defconfig"
    else
      MAKCFG=bcm2712_defconfig
    fi
    KRNLID="2712"
    OLDIMG="kernel_2712.img"
    ;;

  *)
    errexit "Invalid configuration"
    ;;

esac
if [[ "${XCOMPILE}" = "FALSE" &&\
 ((("${KRNLID}" = "v8" || "${KRNLID}" = "2712") && "${ARCH_K}" != "aarch64") ||\
 (("${KRNLID}" != "v8" && "${KRNLID}" != "2712") && "${ARCH_K}" = "aarch64") ||\
 (("${KRNLID}" = "v8" || "${KRNLID}" = "2712") && "${ARCH_U}" != "arm64") ||\
 (("${KRNLID}" != "v8" && "${KRNLID}" != "2712") && "${ARCH_U}" = "arm64")) ]]; then
  errexit "Local builds require similar kernel and userland architectures: use cross-compile mode (-x,--cross-compile) instead"
fi
instpkgs bc bison flex git libc6-dev libncurses5-dev libssl-dev make wget
if [ "${XCOMPILE}" = "TRUE" ]; then
  instpkgs crossbuild-essential-armhf crossbuild-essential-arm64
fi
if [[ "${UNATND}" = "FALSE" && "${BRANCH}" = "" ]]; then
  echo ""
  echo -n "Branch (commitid/current/default/rpi-M.N.y): "
  read -r BRANCH
fi
BRANCH="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${BRANCH}")"
if [ "${BRANCH}" = "" ]; then
  BRANCH="current"
fi
if [[ "${BRANCH}" = "current" && "${RASPI}" = "FALSE" ]]; then
  errexit "Building 'current' branch requires a Raspberry Pi"
fi
if [[ ! "${BRANCH}" =~ ^[[:xdigit:]]+$ && "${BRANCH}" != "current" && "${BRANCH}" != "default" &&\
 "${BRANCH}" != "$(git ls-remote --symref https://github.com/raspberrypi/linux | sed -n "s|^\S\+\s\+refs/heads/\(${BRANCH}\)$|\1|p")" ]]; then
  errexit "Branch '${BRANCH}' does not exist"
fi
if [[ "${UNATND}" = "FALSE" && "${SUFFIX}" = "" ]]; then
  echo ""
  echo -n "Suffix (blank = none): "
  read -r SUFFIX
fi
SUFFIX="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${SUFFIX}")"
SUFFIX="$(tr [[:blank:]] _ <<< "${SUFFIX}")"
if [[ "${UNATND}" = "FALSE" && "${OLDBOOT}" = "FALSE" ]]; then
  echo ""
  echo -n "Use old boot mount (/boot) (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        OLDBOOT=TRUE
      fi
      break
    fi
  done
fi
if [[ "${XCOMPILE}" = "FALSE" && "${UNATND}" = "FALSE" && "${OLDBOOT}" = "FALSE" && "${NOINITRAMFS}" = "FALSE" ]]; then
  echo ""
  echo -n "Disable running update-initramfs (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        NOINITRAMFS=TRUE
      fi
      break
    fi
  done
fi
if [[ "${UNATND}" = "FALSE" && "${JOBS}" = "" ]]; then
  echo ""
  echo -n "Number of jobs (blank = 4): "
  read -r JOBS
fi
JOBS="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${JOBS}")"
if [ "${JOBS}" = "" ]; then
  JOBS=4
fi
if [[ (! "${JOBS}" =~ ^[[:digit:]]+$) || (${JOBS} -eq 0) ]]; then
  errexit "Invalid number of jobs"
fi
if [[ "${UNATND}" = "FALSE" && "${MNUCFG}" = "FALSE" ]]; then
  echo ""
  echo -n "Run menuconfig (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        MNUCFG=TRUE
      fi
      break
    fi
  done
fi
if [[ "${UNATND}" = "FALSE" && "${INTERACTIVE}" = "FALSE" ]]; then
  echo ""
  echo -n "Interactive shell before compile (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        INTERACTIVE=TRUE
      fi
      break
    fi
  done
fi
if [[ "${XCOMPILE}" = "FALSE" && "${UNATND}" = "FALSE" && "${OLDBOOT}" = "TRUE" && "${KEEP}" = "FALSE" ]]; then
  echo ""
  echo -n "Keep old kernel as .bak (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        KEEP=TRUE
      fi
      break
    fi
  done
fi
if [[ "${UNATND}" = "FALSE" && "${PURGE}" = "FALSE" ]]; then
  echo ""
  echo -n "Purge source files upon completion (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        PURGE=TRUE
      fi
      break
    fi
  done
fi
if [[ "${XCOMPILE}" = "FALSE" && "${UNATND}" = "FALSE" && "${REBOOT}" = "FALSE" ]]; then
  echo ""
  echo -n "Reboot upon completion (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [yY] ]]; then
        REBOOT=TRUE
      fi
      break
    fi
  done
fi
echo ""
echo -n "Configuration: "
case "${CONFIG}" in

  1)
    echo "${CONFIG1}"
    ;;

  2)
    echo "${CONFIG2}"
    ;;

  3)
    echo "${CONFIG3}"
    ;;

  4)
    echo "${CONFIG4}"
    ;;

  5)
    echo "${CONFIG5}"
    ;;

esac
echo "$(dispyn "Cross-compile mode" "${XCOMPILE}")"
echo "Branch: ${BRANCH}"
echo -n "Suffix: "
if [ "${SUFFIX}" = "" ]; then
  echo "none"
else
  echo "${SUFFIX}"
fi
echo "$(dispyn "Use old boot mount (/boot)" "${OLDBOOT}")"
echo "$(dispyn "Disable running update-initramfs" "${NOINITRAMFS}")"
echo "Jobs: ${JOBS}"
echo "$(dispyn "Run menuconfig" "${MNUCFG}")"
echo "$(dispyn "Interactive shell" "${INTERACTIVE}")"
if [[ "${XCOMPILE}" = "FALSE" && "${OLDBOOT}" = "TRUE" ]]; then
  echo "$(dispyn "Keep old kernel as .bak" "${KEEP}")"
fi
echo "$(dispyn "Purge source files upon completion" "${PURGE}")"
if [ "${XCOMPILE}" = "FALSE" ]; then
  echo "$(dispyn "Reboot upon completion" "${REBOOT}")"
fi
if [ "${UNATND}" = "FALSE" ]; then
  echo ""
  echo -n "Build kernel (y/n)? "
  while read -r -n 1 -s answer; do
    if [[ ${answer} = [yYnN] ]]; then
      echo "${answer}"
      if [[ ${answer} = [nN] ]]; then
        errexit "Aborted"
      fi
      break
    fi
  done
fi
if [ -d /usr/src/linux ]; then
  SOURCE="$(sed -n 's|^\[branch "\(.*\)"\]|\1|p' /usr/src/linux/.git/config 2> /dev/null)"
  TARGET="${BRANCH}"
  if [ "${TARGET}" = "default" ]; then
    TARGET="$(git ls-remote --symref https://github.com/raspberrypi/linux | head -n 1 | sed -n 's|^ref:\s\+refs/heads/\(.*\)\s\+HEAD$|\1|p')"
  fi
  if [ "${TARGET}" != "${SOURCE}" ]; then
    DELETE=TRUE
  fi
  if [[ "${UNATND}" = "FALSE" && "${DELETE}" = "FALSE" ]]; then
    echo ""
    echo -n "Delete existing source files [Source/Target branch = ${SOURCE}] (y/n)? "
    while read -r -n 1 -s answer; do
      if [[ ${answer} = [yYnN] ]]; then
        echo "${answer}"
        if [[ ${answer} = [yY] ]]; then
          DELETE=TRUE
        fi
        break
      fi
    done
  fi
  if [ "${DELETE}" = "TRUE" ]; then
    echo ""
    echo "Deleting existing source files"
    rm -r /usr/src/linux
  fi
fi
if [ -d /usr/src/linux ]; then
  if [[ ! "${BRANCH}" =~ ^[[:xdigit:]]+$ && "${BRANCH}" != "current" ]]; then
    if [[ "${UNATND}" = "FALSE" && "${FRESHEN}" = "FALSE" ]]; then
      echo ""
      echo -n "Freshen existing source files (y/n)? "
      while read -r -n 1 -s answer; do
        if [[ ${answer} = [yYnN] ]]; then
          echo "${answer}"
          if [[ ${answer} = [yY] ]]; then
            FRESHEN=TRUE
          fi
          break
        fi
      done
    fi
    if [ "${FRESHEN}" = "TRUE" ]; then
      cd /usr/src/linux
      echo ""
      echo "Freshening existing source files"
      OUTPUT="$(mktemp)"
      if [ $? -ne 0 ]; then
        errexit "mktemp failed"
      fi
      git pull --ff-only origin "${SOURCE}" 2>&1 | tee "${OUTPUT}"
      grep -i 'Already up to date\|fatal' "${OUTPUT}" &> /dev/null
      RESULT=$?
      rm "${OUTPUT}"
      if [ ${RESULT} -eq 0 ]; then
        errexit "Exiting"
      fi
    fi
  fi
else
  cd /usr/src
  echo ""
  echo "Downloading source files (this may take a while)"
  if [[ "${BRANCH}" =~ ^[[:xdigit:]]+$ || "${BRANCH}" = "current" ]]; then
    SRCDIR="$(mktemp --directory --tmpdir build-kernel-srcdir-XXXXX)"
    if [ $? -ne 0 ]; then
      errexit "mktemp failed"
    fi
    if [[ "${BRANCH}" =~ ^[[:xdigit:]]+$ ]]; then
      wget -q -O ${SRCDIR}/linux-${BRANCH}.tar.gz https://github.com/raspberrypi/linux/archive/${BRANCH}.tar.gz
      RESULT=$?
      if [ ${RESULT} -eq 0 ]; then
        tar xfz ${SRCDIR}/linux-${BRANCH}.tar.gz -C ${SRCDIR}
        rm ${SRCDIR}/linux-${BRANCH}.tar.gz
      fi
    else
      wget -q -O /usr/local/bin/rpi-source https://raw.githubusercontent.com/RPi-Distro/rpi-source/master/rpi-source &&\
 chmod +x /usr/local/bin/rpi-source && /usr/local/bin/rpi-source -q --tag-update && /usr/local/bin/rpi-source --quiet --dest ${SRCDIR} --delete --nomake
      RESULT=$?
    fi
    if [ ${RESULT} -ne 0 ]; then
      errexit "Unable to download ${BRANCH} branch"
    fi
    COMMITID="$(ls ${SRCDIR} | sed -n 's/linux-\([[:xdigit:]]\{40\}\)/\1/p')"
    rm -r /usr/src/linux &> /dev/null
    mv ${SRCDIR}/linux-${COMMITID} /usr/src/linux
    rm -r ${SRCDIR}
    SRCDIR=""
    mkdir /usr/src/linux/.git
    echo "[branch \"${BRANCH}\"]" > /usr/src/linux/.git/config
  elif [ "${BRANCH}" = "default" ]; then
    git clone --quiet --depth=1 https://github.com/raspberrypi/linux
  else
    git clone --quiet --depth=1 --branch "${BRANCH}" https://github.com/raspberrypi/linux
  fi
fi
cd /usr/src/linux
echo ""
make ${MAKCFG}
if [ "${SUFFIX}" != "" ]; then
  sed -i "s|^\(CONFIG_LOCALVERSION=\".*\)\"$|\1-${SUFFIX}\"|" .config
fi
if [ "${MNUCFG}" = "TRUE" ]; then
  if [ "${XCOMPILE}" = "TRUE" ]; then
    if [[ "${KRNLID}" = "v8" || "${KRNLID}" = "2712" ]]; then
      make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- menuconfig
    else
      make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- menuconfig
    fi
  else
    make menuconfig
  fi
fi
if [ "${INTERACTIVE}" = "TRUE" ]; then
  echo ""
  echo "Launching BASH shell"
  echo "Use exit or ^D to resume"
  echo ""
  /bin/bash -i
fi
echo ""
BUILD="$(sed -n 's|^.*\s\+\(\S\+\.\S\+\.\S\+\)\s\+Kernel Configuration$|\1|p' .config)-rpi999-rpi-${KRNLID}"
if [ "${XCOMPILE}" = "TRUE" ]; then
  DSTDIR="$(mktemp --directory --tmpdir build-kernel-dstdir-XXXXX)"
  if [ $? -ne 0 ]; then
    errexit "mktemp failed"
  fi
  if [[ "${KRNLID}" = "v8" || "${KRNLID}" = "2712" ]]; then
    if [ "${OLDBOOT}" = "FALSE" ]; then
      make -j ${JOBS} KERNELRELEASE="${BUILD}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image.gz modules dtbs
      env PATH=$PATH make KERNELRELEASE="${BUILD}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- INSTALL_MOD_PATH=${DSTDIR} modules_install
      mkdir -p "${DSTDIR}/boot/firmware/overlays/"
      mkdir -p "${DSTDIR}/lib/linux-image-${BUILD}/broadcom/"
      mkdir -p "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp .config "${DSTDIR}/boot/config-${BUILD}"
      echo "ffffffffffffffff B The real System.map is in the linux-image-<version>-dbg package" > "${DSTDIR}/boot/System.map-${BUILD}"
      cp arch/arm64/boot/Image.gz "${DSTDIR}/boot/vmlinuz-${BUILD}"
      cp arch/arm64/boot/dts/broadcom/*.dtb "${DSTDIR}/lib/linux-image-${BUILD}/broadcom/"
      cp arch/arm64/boot/dts/overlays/*.dtb* "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm64/boot/dts/overlays/README "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm64/boot/Image.gz "${DSTDIR}/boot/firmware/${OLDIMG}"
      cp arch/arm64/boot/dts/broadcom/*.dtb "${DSTDIR}/boot/firmware/"
      cp arch/arm64/boot/dts/overlays/*.dtb* "${DSTDIR}/boot/firmware/overlays/"
      cp arch/arm64/boot/dts/overlays/README "${DSTDIR}/boot/firmware/overlays/"
    else
      make -j ${JOBS} ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image.gz modules dtbs
      env PATH=$PATH make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- INSTALL_MOD_PATH=${DSTDIR} modules_install
      mkdir -p "${DSTDIR}/boot/overlays/"
      cp arch/arm64/boot/Image.gz "${DSTDIR}/boot/${OLDIMG}"
      cp arch/arm64/boot/dts/broadcom/*.dtb "${DSTDIR}/boot/"
      cp arch/arm64/boot/dts/overlays/*.dtb* "${DSTDIR}/boot/overlays/"
      cp arch/arm64/boot/dts/overlays/README "${DSTDIR}/boot/overlays/"
    fi
  else
    if [ "${OLDBOOT}" = "FALSE" ]; then
      make -j ${JOBS} KERNELRELEASE="${BUILD}" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- zImage modules dtbs
      env PATH=$PATH make KERNELRELEASE="${BUILD}" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- INSTALL_MOD_PATH=${DSTDIR} modules_install
      mkdir -p "${DSTDIR}/boot/firmware/overlays/"
      mkdir -p "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp .config "${DSTDIR}/boot/config-${BUILD}"
      echo "ffffffffffffffff B The real System.map is in the linux-image-<version>-dbg package" > "${DSTDIR}/boot/System.map-${BUILD}"
      cp arch/arm/boot/zImage "${DSTDIR}/boot/vmlinuz-${BUILD}"
      cp arch/arm/boot/zImage "${DSTDIR}/boot/firmware/${OLDIMG}"
      if [ "$(olddtb)" = "TRUE" ]; then
        cp arch/arm/boot/dts/*.dtb "${DSTDIR}/lib/linux-image-${BUILD}/"
        cp arch/arm/boot/dts/*.dtb "${DSTDIR}/boot/firmware/"
      else
        cp arch/arm/boot/dts/broadcom/*.dtb "${DSTDIR}/lib/linux-image-${BUILD}/"
        cp arch/arm/boot/dts/broadcom/*.dtb "${DSTDIR}/boot/firmware/"
      fi
      cp arch/arm/boot/dts/overlays/*.dtb* "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm/boot/dts/overlays/README "${DSTDIR}/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm/boot/dts/overlays/*.dtb* "${DSTDIR}/boot/firmware/overlays/"
      cp arch/arm/boot/dts/overlays/README "${DSTDIR}/boot/firmware/overlays/"
    else
      make -j ${JOBS} ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- zImage modules dtbs
      env PATH=$PATH make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- INSTALL_MOD_PATH=${DSTDIR} modules_install
      mkdir -p "${DSTDIR}/boot/overlays/"
      cp arch/arm/boot/zImage "${DSTDIR}/boot/${OLDIMG}"
      if [ "$(olddtb)" = "TRUE" ]; then
        cp arch/arm/boot/dts/*.dtb "${DSTDIR}/boot/"
      else
        cp arch/arm/boot/dts/broadcom/*.dtb "${DSTDIR}/boot/"
      fi
      cp arch/arm/boot/dts/overlays/*.dtb* "${DSTDIR}/boot/overlays/"
      cp arch/arm/boot/dts/overlays/README "${DSTDIR}/boot/overlays/"
    fi
  fi
  ARCHIVE="kernel-$(sed -n 's|^.*\s\+\(\S\+\.\S\+\.\S\+\)\s\+Kernel Configuration$|\1|p' .config)$(sed -n 's|^CONFIG_LOCALVERSION=\"\(.*\)\"$|\1|p' .config).zip"
  cd "${DSTDIR}"
  find lib -type l -exec rm {} \;
  zip -q -r "${ARCHIVE}" *
  if [ "${OUTDIR}" != "" ]; then
    if [ "${OUTDIR: -1}" != "/" ]; then
      OUTDIR+="/"
    fi
  else
    if [ "${REALUSER}" = "root" ]; then
      OUTDIR="/root/"
    else
      OUTDIR="/home/${REALUSER}/"
    fi
  fi
  chown "${REALUSER}:${REALUSER}" "${ARCHIVE}"
  cd "${CURDIR}"
  mv "${DSTDIR}/${ARCHIVE}" "${OUTDIR}"
  rm -r "${DSTDIR}"
  DSTDIR=""
else
  if [[ "${KRNLID}" = "v8" || "${KRNLID}" = "2712" ]]; then
    if [ "${OLDBOOT}" = "FALSE" ]; then
      make -j ${JOBS} KERNELRELEASE="${BUILD}" Image.gz modules dtbs
      make KERNELRELEASE="${BUILD}" modules_install
      mkdir -p /boot/firmware/overlays/
      mkdir -p "/lib/linux-image-${BUILD}/broadcom/"
      mkdir -p "/lib/linux-image-${BUILD}/overlays/"
      cp .config "/boot/config-${BUILD}"
      echo "ffffffffffffffff B The real System.map is in the linux-image-<version>-dbg package" > "/boot/System.map-${BUILD}"
      cp arch/arm64/boot/Image.gz "/boot/vmlinuz-${BUILD}"
      cp arch/arm64/boot/dts/broadcom/*.dtb "/lib/linux-image-${BUILD}/broadcom/"
      cp arch/arm64/boot/dts/overlays/*.dtb* "/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm64/boot/dts/overlays/README "/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm64/boot/Image.gz "/boot/firmware/${OLDIMG}"
      cp arch/arm64/boot/dts/broadcom/*.dtb "/boot/firmware/"
      cp arch/arm64/boot/dts/overlays/*.dtb* "/boot/firmware/overlays/"
      cp arch/arm64/boot/dts/overlays/README "/boot/firmware/overlays/"
      if [ "${NOINITRAMFS}" = "FALSE" ]; then
        update-initramfs -c -v -k "${BUILD}"
      fi
    else
      make -j ${JOBS} Image.gz modules dtbs
      make modules_install
      if [ "${KEEP}" = "TRUE" ]; then
        mv "/boot/${OLDIMG}" "/boot/${OLDIMG}.bak"
      fi
      cp arch/arm64/boot/Image.gz "/boot/${OLDIMG}"
      cp arch/arm64/boot/dts/broadcom/*.dtb /boot/
      cp arch/arm64/boot/dts/overlays/*.dtb* /boot/overlays/
      cp arch/arm64/boot/dts/overlays/README /boot/overlays/
    fi
  else
    if [ "${OLDBOOT}" = "FALSE" ]; then
      make -j ${JOBS} KERNELRELEASE="${BUILD}" zImage modules dtbs
      make KERNELRELEASE="${BUILD}" modules_install
      mkdir -p /boot/firmware/overlays/
      mkdir -p "/lib/linux-image-${BUILD}/overlays/"
      cp .config "/boot/config-${BUILD}"
      echo "ffffffffffffffff B The real System.map is in the linux-image-<version>-dbg package" > "/boot/System.map-${BUILD}"
      cp arch/arm/boot/zImage "/boot/vmlinuz-${BUILD}"
      cp arch/arm/boot/zImage "/boot/firmware/${OLDIMG}"
      if [ "$(olddtb)" = "TRUE" ]; then
        cp arch/arm/boot/dts/*.dtb "/lib/linux-image-${BUILD}/"
        cp arch/arm/boot/dts/*.dtb "/boot/firmware/"
      else
        cp arch/arm/boot/dts/broadcom/*.dtb "/lib/linux-image-${BUILD}/"
        cp arch/arm/boot/dts/broadcom/*.dtb "/boot/firmware/"
      fi
      cp arch/arm/boot/dts/overlays/*.dtb* "/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm/boot/dts/overlays/README "/lib/linux-image-${BUILD}/overlays/"
      cp arch/arm/boot/dts/overlays/*.dtb* "/boot/firmware/overlays/"
      cp arch/arm/boot/dts/overlays/README "/boot/firmware/overlays/"
      if [ "${NOINITRAMFS}" = "FALSE" ]; then
        update-initramfs -c -v -k "${BUILD}"
      fi
    else
      make -j ${JOBS} zImage modules dtbs
      make modules_install
      if [ "${KEEP}" = "TRUE" ]; then
        mv "/boot/${OLDIMG}" "/boot/${OLDIMG}.bak"
      fi
      cp arch/arm/boot/zImage "/boot/${OLDIMG}"
      if [ "$(olddtb)" = "TRUE" ]; then
        cp arch/arm/boot/dts/*.dtb /boot/
      else
        cp arch/arm/boot/dts/broadcom/*.dtb /boot/
      fi
      cp arch/arm/boot/dts/overlays/*.dtb* /boot/overlays/
      cp arch/arm/boot/dts/overlays/README /boot/overlays/
    fi
  fi
fi
echo ""
echo "Kernel successfully built"
if [ "${PURGE}" = "TRUE" ]; then
  echo ""
  echo "Purging source files"
  rm -r /usr/src/linux
fi
if [ "${XCOMPILE}" = "FALSE" ]; then
  echo ""
  if [ "${REBOOT}" = "TRUE" ]; then
    echo "Rebooting"
    echo ""
    shutdown -r now
  else
    echo "Reboot required to use new kernel"
    if [ "${UNATND}" = "FALSE" ]; then
      echo ""
      echo -n "Reboot now (y/n)? "
      while read -r -n 1 -s answer; do
        if [[ ${answer} = [yYnN] ]]; then
          echo "${answer}"
          if [[ ${answer} = [yY] ]]; then
            shutdown -r now
          fi
          break
        fi
      done
    fi
  fi
fi
echo ""
