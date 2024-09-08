# Amity
Home theater control over HDMI-CEC

## Introduction

Use a Raspberry Pi, and a Siri Remote to control a home theater system over HDMI-CEC.

## Caveats

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

Amity requires splicing into the HDMI-CEC connection between the TV and the receiver. Right now, this requires carefully stripping, and cutting the correct wires in an HDMI cable so they can be wired in to Raspberry Pi GPIO pins. HDMI-CEC specifies the use of a 27K ohms pullup resistors for the CEC wires. The GPIO pins used by Amity are configured, in software, to enable the internal Raspberry Pi ~60K ohms pullup resistors. This is wildly out of spec. for HDMI-CEC but has worked well for me. It is possible to build the correct circuit with external resistors, but I haven't had a need so far. Wiring the Raspberry Pi incorrectly into the HDMI cable may also damage your HDMI equipment and/or Raspberry Pi.

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

HDMI-CEC is a terrible control protocol. Different equipment manufacturers implement it in often incompatible ways. Some HDMI devices don't support HDMI-CEC at all. HDMI-CEC devices often behave unpredictably, and it can be an endless source of headaches. Using HDMI-CEC for anything is a very bad idea.

Amity is designed to work with a traditional setup centered around a receiver. For example, a TV connected to a receiver output, and various playback devices (i.e. media streamers, blu-ray devices, and game consoles) connected to the receiver's inputs. When changing the source, the input is changed on the receiver. HDMI-CEC only allows the designated TV to select arbitrary sources. TVs will not heed source selection commands from any other device. As a result, Amity will not be able to control sources connected directly to a TV, including built-in smart TV apps. Similarly, Amity does not support HDMI ARC/eARC. If you use smart TV apps or connect devices, other than a receiver, directly to the TV inputs, Amity is not for your system.

At present, Amity can be considered a proof of concept because of the limited set of equipment it has been tested with. It may work flawlessly with your equipment, or it may very well not. There may be ways to fix issues you encounter, and there may not. HDMI-CEC is arbitrary, and capricious. As Amity is tested with more equipment, its utility will become clearer.

Equipment that is known to be compatible with Amity:

- LG OLED TV
- Denon AVR-X3400H
- Apple TV 4K
- Sony Playstation 5
- Amazon Fire TV (media player)
- Nintendo Switch (see [Strange Devices](#strange-devices))

## Prerequisites

* A Raspberry Pi 3 Model B+, or Pi Zero 2 W, or newer with an appropriate power supply, that can run 64-bit Linux. Network connectivity is required for initial setup but not when controlling your home theater.
* A remote control. An unpaired Siri Remote. Preferably, a Gen 2 or Gen 3 remote (aluminum case with a power button in the top right corner), but a Gen 1 remote (black top) can also work. Or an Amazon Fire TV remote, or common third party RF remotes that behave like keyboards. IR remotes are not supported.
* An HDMI-CEC splice (either a stripped, spliced cable, or a dedicated board and an extra HDMI cable)

## Setup

### HDMI Splice

Amity does not work with the Raspberry Pi's HDMI connectors. Amity works by emulating a TV to the receiver, and all the devices connected to it, and by emulating a single playback device to the TV. This is done by splicing into the HDMI-CEC bus between the receiver, and the TV. Splicing requires either stripping an existing HDMI cable, carefully pulling out the CEC, and ground wires without disturbing the other wires in the cable, and connecting them to Raspberry Pi GPIO pins or using a HDMI-CEC breakout board that preserves, and passes through the HDMI A/V signals without noticeably degrading them.

If stripping an HDMI cable, cut the CEC wire to create two ends that connect to the Raspberry Pi. DO NOT cut the ground wire - connect a wire from the Raspberry Pi ground to the intact ground wire.

Whether with a cable or a breakout board, with power off, connect the two CEC wires (one connected to the TV, and the other connected to the receiver) to GPIO pins 23 and 24 on the Raspberry Pi (order doesn't matter). Connect the HDMI splice ground to ground on the Raspberry Pi. These are pins 14, 16, and 18 on the Raspberry Pi [pinout](https://pinout.xyz). Be careful not to miswire the two CEC wires to ground as that could potentially damage the HDMI equipment and the Raspberry Pi!

### Initial Installation

Amity setup, and configuration is done entirely in the command terminal, and requires some familiarity with the terminal.

It is assumed that this will be a dedicated device for home theater control. It may be possible to run Amity with other services on the same RPi but it is not supported, and is strongly discouraged.

1. Image Raspberry Pi a 64-bit image **without** Desktop (the Lite image) on a MicroSD card. The best tool for this is [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Desktop **MUST NOT** be installed.
2. Insert the MicroSD into the Rpi, power it on, and login via SSH, and use the console (unless configured differently, the default user created by Raspberry Pi Imager is `pi`. All examples will assume the user is `pi`)
3. Copy the line below, paste it into the terminal, and press enter. This will perform some initial configuration of the system, and install Amity. It may take a while. Once complete, there will be a new sub directory `amity`, i.e. `/home/pi/amity`

    ```commandline
    /bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/retsyx/amity/main/setup_amity)"
    ```

Amity requires a Linux kernel compiled with `cec-gpio` support enabled. If the running kernel doesn't support `cec-gpio` (it likely doesn't), then Amity will download, and install an appropriate pre-compiled kernel, and then reboot. If the running kernel already supports `cec-gpio`, Amity will not replace it.

### Using a Keyboard for Control

Some media remote controls (Amazon Fire, or common third party RF remotes) operate as keyboards. Amity can be controlled with these remotes after they have been installed or paired to the Raspberry Pi. For Bluetooth remotes (like Amazon Fire) use `bluetoothctl` for pairing. For generic RF remotes, that typically come with a USB dongle, plug in the dongle. Amazon Fire, remotes are recommended as they are typically cheaper, and operate in well defined ways. Generic remotes can be peculiar, and may not work for arbitrary reasons. For example, some remotes have a power button that doesn't generate a key press. IR remotes are not supported.

This document uses the Siri remote as an example, but remote operation (except pairing) is similar in all cases. In particular, Amity uses the direction buttons for activity selection. Amazon Fire activity buttons are undocumented, and are not supported.

### Pairing a Siri Remote

The preferred method of control is a Siri Remote (easy pairing, and great battery life!). The remote **MUST** be unpaired from any other device. If the remote is paired to another device, like an Apple TV, or Mac, it will fail to work with Amity in unpredictable ways. Ensure the remote is charged.

In the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Then, to pair the remote, enter:

```commandline
./pair_remote
```

Hold the remote near the Raspberry Pi and simultaneously press the Menu/Back and the Volume Up (+) buttons for a couple seconds. Follow the prompts.

If successful, then the remote has been paired, and is ready for use. In addition, Amity's `config.yaml` file was updated. More about `config.yaml` in the next section.

### HDMI Configuration

Amity uses a concept of activities to organize the different uses of a home theater system, similar to Harmony remotes. Every activity has a source device (i.e. Apple TV, or PlayStation), an audio output device (i.e. a receiver, or TV for volume commands), an HDMI input switching device (i.e. a receiver, or TV), and a display (typically a TV). Amity supports up to 5 activities (because that is the number of buttons available on Siri remotes).

Configuring activities is fairly straightforward thanks to HDMI-CEC.

#### Quick Sanity Scan

Ensure that all home theater devices have HDMI-CEC enabled, and are discoverable. To list all the devices available on HDMI-CEC, in the Amity directory, run:

```commandline
./configure_hdmi scan
```

The names of the devices are their HDMI On Screen Display (OSD) names, and are used to reference the devices in Amity configuration. Ensure that no two devices share the same name. Duplicate names are not supported, and will lead to confusion, failure, and disappointment.

Devices that don't appear in the list don't have HDMI-CEC enabled or have a very broken HDMI-CEC implementation (i.e. Nintendo Switch) that may only partially work in general.

If you don't see any devices, ensure the HDMI-CEC splice cable is correctly attached.

#### Automatic Activity Recommendation

Now that all the devices are accounted for, Amity can generate a set of recommended activities:

```commandline
./configure_hdmi recommend
```

The activity configuration was written into `config.yaml` in the Amity directory (i.e. `~/amity/config.yaml`). Open `config.yaml` with your favorite text editor.

#### Editing config.yaml

Here's an example `config.yaml` with two activities:

```yaml
adapters:
    front: /dev/cec1
    back: /dev/cec0
remote:
    mac: 12:34:56:78:9A:BC
activities:
    - name: Watch Living Room
      display: TV
      source: Living Room
      audio: AVR-X3400H
    - name: Play PlayStation 5
      display: TV
      source: PlayStation 5
      audio: AVR-X3400H
```

At the top is an `adapters` section with the cec-gpio devices Amity discovered. The `front` adapter is connected to the TV (Amity pretending to be a playback device), the `back` adapter is connected to the receiver (Amity pretending to be a TV).

After is a `remote` section with the mac address of the paired remote. Below is the `activities` section with the activities that Amity guessed. The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities. More on this in the [usage](#usage) topic.

Let's look at one activity in detail:


```yaml
- name: Watch Living Room
  display: TV
  source: Living Room
  audio: AVR-X3400H
```

The fields are:

* `name` - this can be anything you want.
* `display` - the HDMI OSD name of the display device. Typically a TV.
* `source` - the HDMI OSD name of the AV source device.
* `audio` - the HDMI OSD name of the audio output device, typically a receiver.

Amity configured an activity with a source device called 'Living Room', using the TV as a display, and the audio receiver for audio output. 'Living Room' is the OSD name of the Apple TV in the living room. The name of the activity can be changed to 'Watch TV' for convenience. The activity name is used with [HomeKit](#homekit).

And that's it... Amity is now fully configured with a paired remote, and two activities for watching Apple TV, and playing with a PlayStation 5. Let's start it!

## Starting Amity

To start Amity, type:

```commandline
./setup_amity enable
```

After this command Amity will run. Close the terminal, and start playing with the remote.

## Stopping Amity

To change configuration, or pair a different remote, Amity must be stopped. To stop Amity, and to prevent it from starting at every system start, type:

```commandline
./setup_amity disable
```

## Usage

Amity has two basic modes, standby, when the home theater is in standby, and active when an activity has been selected.

### Standby

In standby, 1 of 5 activities can be started. On a Gen 2 remote, the 5 activities are assigned to the select, and directional buttons - select, up, right, down, left. Note the order listed here matches the order of activities as specified in `config.yaml`. The select button starts the first activity, up the second, right the third, and so on. On a Gen 1 remote, there are no directional keys. Instead, press the touchpad (making a click) on the part of the touchpad that corresponds to the direction. Press the center for the first activity, towards the top of the touchpad for the second activity, towards the right for the third activity, and so on.

On a Gen 2 remote, pressing the power button will send a standby signal to all devices. This is useful, if a device is on when it shouldn't be. Gen 1 remotes don't have a power button. Instead, use a triple tap (not press) on the touchpad to signal a power button press.

After an activity has been selected, the remote transitions into the active mode.

### Active

When active, all the buttons should behave as expected for the selected activity. For example, when using a PlayStation, the directional buttons navigate the PlayStation interface, select selects, back/menu backs out, and volume controls control the audio device. Touchpad swipes can also be used. This is especially important for Gen 1 remotes without directional buttons.

On a Gen 2, or later, remote press the power button to end the activity and put the system in standby. On Gen 1 remotes, triple tap (not press) on the touchpad to signal a power button press, to end the activity, and put the system in standby.

On a Gen 2, or later, remote press the power button, and one of the activity selection buttons (select, and directional) at the same time, to jump directly from one activity to another, without putting the system in standby.

## Strange Devices

Many HDMI-CEC devices do strange things. Here are some known workarounds.

### Nintendo Switch

The Nintendo switch has a minimal HDMI-CEC implementation that appears to be nearly always dormant and ignores practically every command except standby. The Switch only appears when it is powered on directly by the user, or placed in the cradle, and then it automatically requests to be displayed.

As a result, the Switch will often not show up in bus scans, or be auto-configured. The solution is to edit `config.yaml` manually to add an activity for the switch. When active, the Switch defaults to calling itself `NintendoSwitch`, so an example activity configuration for a Switch would be:

```yaml
- name: Play Switch
  display: TV
  source: NintendoSwitch
  audio: AVR-X3400H
```

Then to play, you would turn on the Switch, and select the `Play Switch` activity on the Siri remote. Amity will do the right thing when the Switch is woken up, and announces itself. To end the activity, press the power button on the Siri remote to place the entire system in standby, including the Switch, which will go dormant again.

Sometimes, however, this may not be enough, and the Switch may still not announce its presence. For this case, if the receiver supports selecting inputs over HDMI-CEC, Amity can be configured to select the input on the receiver. The configuration:

```yaml
- name: Play Switch
  display: TV
  source: NintendoSwitch
  audio: AVR-X3400H
  switch:
    device: AVR-X3400H
    input: 6
```

This tells Amity that the input switching device is the AVR, and that the HDMI input to use is input 6. When selecting the `Play Switch` activity, Amity will tell the AVR to switch to input 6. This depends on the AVR supporting the feature, and on finding the correct value for the input, 6 in this case. Finding the input number is through trial, and error, at the moment. On a Denon AVR-X3400H the input values are:

1. CBL/SAT
2. DVD
3. Blu-ray
4. Games
5. Media Player
6. Aux 2
7. ?
8. Aux 1

?. CD

## HomeKit

Amity can be integrated with HomeKit as a TV accessory. This allows controlling Amity with Siri, and integrating Amity into HomeKit automations.

It is highly recommended to complete all HDMI configuration, and setup before adding Amity into HomeKit.

### Enabling HomeKit

Enabling HomeKit (if not already enabled) will restart Amity.

In the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Then, to enable HomeKit support, enter:

```commandline
./configure_homekit enable
```

If Amity is not already paired to your Home, then the QR code and setup code required to add Amity into your Home will be displayed. In the iOS Home app, tap to add an accessory and either scan the QR code, or enter the setup code manually.

If, for some reason, you need to re-display the most recent pairing code, use the command:

```commandline
./configure_homekit code
```

### Disabling HomeKit

Disabling HomeKit (if not already disabled) will restart Amity.

In the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Then, to disable HomeKit support, enter:

```commandline
./configure_homekit disable
```

### Resetting HomeKit Configuration

This will reset Amity's HomeKit state, and restart Amity, if necessary. To re-add Amity, you will need to remove Amity in the iOS Home app, and add Amity as a new accessory.

In the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Then, to reset HomeKit configuration, enter:

```commandline
./configure_homekit reset
```

If HomeKit support is still enabled, then the new QR code and setup code required to add Amity into your home will be displayed.

## License

Amity source code is licensed under the [GPLv3](LICENSE).
