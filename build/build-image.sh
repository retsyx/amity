#!/bin/bash

set -xe

COMPILE_KERNEL=YES

usage()
{
  cat <<EOF

Usage: $0 [options]
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

# All systems define UID?
if [ "$UID" = "" ]; then
    UID=$(id -u)
fi

# Some systems define GID, and some don't?
if [ "$GID" = "" ]; then
    GID=$(id -g)
fi

sudo chown $UID:$GID amity.img
xz --force amity.img

popd