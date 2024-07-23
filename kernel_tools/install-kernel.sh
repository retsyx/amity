#!/bin/bash

# Written by RonR: https://forums.raspberrypi.com/viewtopic.php?t=343387

trap '{ stty sane; echo ""; errexit "Aborted"; }' SIGINT SIGTERM

errexit()
{
  echo ""
  echo "$1"
  echo ""
  exit 1
}

usage()
{
  cat <<EOF

Usage: $0 [options] <kernel-archive>
-h,--help            This usage description
-n,--noinitramfs     Disable running update-initramfs
-r,--reboot          Reboot upon completion

EOF
}

if [ $(id -u) -ne 0 ]; then
  errexit "Must be run as root user: sudo $0"
fi
PGMNAME="$(basename $0)"
for PID in $(pidof -x -o %PPID "${PGMNAME}"); do
  if [ ${PID} -ne $$ ]; then
    errexit "${PGMNAME} is already running"
  fi
done
ARCHIVE=""
NOINITRAMFS=FALSE
REBOOT=FALSE
while [ $# -gt 0 ]; do
  case "$1" in

    -h|--help)
      usage
      exit
      ;;

    -n|--noinitramfs)
      NOINITRAMFS=TRUE
      shift
      ;;

    -r|--reboot)
      REBOOT=TRUE
      shift
      ;;

    -*|--*)
      errexit "Unrecognized option"
      ;;

    *)
      ARCHIVE="$1"
      ARCHIVE="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${ARCHIVE}")"
      shift
      ;;

  esac
done
if [ "${ARCHIVE}" = "" ]; then
  usage
  exit
fi
if [ ! -f "${ARCHIVE}" ]; then
  errexit "${ARCHIVE} not found"
fi
unzip -tq "${ARCHIVE}" > /dev/null
if [ $? -ne 0 ]; then
  errexit "${ARCHIVE} is not a valid archive"
fi
BUILD="$(unzip -l ${ARCHIVE} boot/vmlinuz-* | sed -n 's|^.*boot/vmlinuz-\(.*\)$|\1|p')"
if [ "${BUILD}" = "" ]; then
  echo ""
  echo "${ARCHIVE} appears to use old boot mount (/boot)"
  NOINITRAMFS=TRUE
fi
if [ "${NOINITRAMFS}" = "TRUE" ]; then
  echo ""
  echo "update-initramfs will not be run"
fi
echo ""
echo -n "Ok to install ${ARCHIVE} (y/n)? "
while read -r -n 1 -s answer; do
  if [[ "${answer}" = [yYnN] ]]; then
    echo "${answer}"
    if [[ "${answer}" = [yY] ]]; then
      break
    else
      errexit "Aborted"
      exit 1
    fi
  fi
done
echo ""
unzip -o "${ARCHIVE}" -d /
if [ $? -ne 0 ]; then
  errexit "unzip ${ARCHIVE} failed"
fi
if [ "${NOINITRAMFS}" = "FALSE" ]; then
  update-initramfs -c -v -k "${BUILD}"
fi
echo ""
echo "Kernel installation completed"
echo ""
if [ "${REBOOT}" = "TRUE" ]; then
  echo "Rebooting"
  echo ""
  shutdown -r now
else
  echo "Reboot required to use new kernel"
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
echo ""
