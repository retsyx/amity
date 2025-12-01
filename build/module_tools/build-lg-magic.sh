set -xe

KERNEL_SRC_DIR=$1
KERNEL_DST_DIR=$2
BUILD_ID=$3

pushd ~

if [ ! -d "lg-magic" ]; then
    git clone https://github.com/retsyx/lg-magic
else
    pushd ~/lg-magic
    git stash && git stash drop || true # cleanup build artifacts
    git fetch && git rebase
    popd
fi

cd lg-magic/kernel

make clean
make -C ${KERNEL_SRC_DIR} M=${PWD} modules

xz --force lg_magic.ko

MODULE_DIR=${KERNEL_DST_DIR}/lib/modules
MODULE_EXTRA_DIR=${MODULE_DIR}/${BUILD_ID}/extra

mkdir -p ${MODULE_EXTRA_DIR}

mv lg_magic.ko.xz ${MODULE_EXTRA_DIR}/.

depmod -b ${KERNEL_DST_DIR} ${BUILD_ID}

popd
