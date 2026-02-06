# Building Amity

Run everything from within the `build` directory.

## Build Environment

The Amity image can be built on a Raspberry Pi but it will be very slow when compiling the required CEC_GPIO enabled Linux kernels. A beefy Ubuntu machine with as many cores as possible is recommended.

To setup the build environment run:

```commandline
./setup-build-env.sh
```

This installs the required system packages and clones the pimod repository.

## Building the Image

```commandline
./build-image.sh -v <VERSION>
```

Where `VERSION` is the release version. Presently, the version is used to populate `amity-os.json` with the assumption that it is hosted as a GitHub release file. For use with Raspberry Pi Imager 2.0 or later.

Output:

* Amity image: `~/amity-build/amity.img.gz`
* Raspberry PI OS list JSON: `~/amity-build/amity-os.json`

## Internals

Building the Amity image consists of several steps:

1. Git clone the Raspberry Pi Linux kernel source code specified in the `kernel-commitid` file.
2. Build two 64-bit Linux kernels with the CEC_GPIO configuration changes specified in the `kernel-config-overlay` file. One for the Raspberry Pi 4 or lesser, and the other for Raspberry Pi 5 or greater.
3. Archive the current Amity source code tree the build script is running in.
4. Run `pimod` with `amity.Pifile` to create the image.
    1. Download the specified base Raspberry Pi OS image.
    2. Install both freshly compiled kernels into the image.
    3. Install the archived Amity source code tree.
    4. Run `build/setup-amity-core.sh` in the image environment to setup Amity.
    5. Perform image cleanup.
5. Compress the image.

