# Amity
Home theater control over HDMI-CEC

## Introduction

Use a Raspberry Pi, and a Siri Remote, or an Amazon Fire TV remote to control a home theater system over HDMI-CEC.

### Why?

A good home theater remote is easy to setup, reliable, simple to use by everyone in the family, has a long battery life, and is reasonably priced. As such, there are no good home theater remotes on the market since Logitech discontinued the Harmony universal remote control family.

Amity came out of a need to replace an aging Logitech Harmony Hub Smart Control system.

### How?

Streamer remotes like the Siri Remote or the Amazon Fire TV remote are high quality, and readily available. They are simple, robust, last a long time on a charge, are very easy to use by everyone in the family, and there is probably one laying unused in a drawer somewhere. So why not use one to control the home theater?

Raspberry Pis are powerful, flexible, readily available, and cheap enough (especially the Pi Zero 2 W).

Most modern home theater components support HDMI-CEC. HDMI-CEC promises easy home theater control but, due to how it is commonly implemented, fails to deliver on the promise. So let's make HDMI-CEC work the way it should (🤞).

### Cost

Amity can be extremely cheap to put together. An example breakdown of costs:

- Raspberry Pi Zero 2 W with headers - $18
- MicroSD card - $10
- Raspberry Pi power adapter - $10
- Amazon Fire TV remote or Siri Remote - Free if you already have an Apple TV or Amazon Fire TV and don't mind losing the voice feature of the remote. Unpair the remote from the streamer, and pair it with Amity instead. Otherwise, ~$25 - $60.
- HDMI cable - $6
- Amity board - ~$16. Boards need to be ordered directly from a PCB manufacturer. PCB manufacturers typically have minimum order counts of a few boards. When ordering 5 boards, the cost per board is ~$16. With larger orders, the cost per board decreases substantially.
- Some Dupont (2.54mm) connector wires - $6

The total cost can be less than $55, if using a stripped HDMI cable, or up to ~$71 with a low volume manufactured Amity board.

## Caveats

### Use Amity at Your Own Risk

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

Amity requires splicing into the HDMI-CEC connection between the TV and the receiver. This requires using a [custom PCB](hw/README.md), or a carefully stripped HDMI cable, so the HDMI-CEC signals can be wired in to Raspberry Pi GPIO pins. Performing the wiring incorrectly may damage your HDMI equipment and/or Raspberry Pi.

Amity may also have terrible bugs.

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

### Amity is Not a Universal Remote Control

Amity is designed for a traditional setup centered around an audio/video receiver (AVR). For example, a TV connected to a receiver output, and various playback devices (i.e. media streamers, blu-ray devices, and game consoles) connected to the receiver's inputs. When changing the source, the input is changed on the receiver. The HDMI-CEC protocol only allows the designated TV to select sources. TVs will not heed arbitrary source selection commands from other devices. As a result, Amity cannot select inputs on a TV, and cannot control sources connected directly to a TV, including built-in smart TV apps. Similarly, Amity does not support HDMI ARC/eARC. If you use smart TV apps or connect devices, other than a receiver, directly to the TV inputs, Amity is not for your system.

For a device to be controlled by Amity, it must support HDMI-CEC.

### Amity is a Proof of Concept

HDMI-CEC is a unevenly implemented by different manufacturers, so it doesn't always work as expected. At present, Amity can be considered a proof of concept because of the limited set of equipment it has been tested with. It works for me. It may work flawlessly with your equipment, or it may very well not. There may be ways to fix issues you encounter, and there may not. As more equipment is tested with Amity, its utility will become clearer.

Equipment that is known to be compatible with Amity:

- LG OLED TV
- Denon AVR-X3400H
- Apple TV 4K
- Sony Playstation 4/5
- Amazon Fire TV (media player)
- Nintendo Switch (see [Strange Devices](#strange-devices))

## Prerequisites

* A Raspberry Pi 3 Model B+, or Pi Zero 2 W, or newer, that can run 64-bit Linux; with an appropriate power supply. Network connectivity is required for initial setup but not when controlling your home theater.
* A MicroSD card.
* A remote control
  * An unpaired Siri Remote. Preferably, a Gen 2 or Gen 3 remote (aluminum case with a power button in the top right corner), but a Gen 1 remote (black top) can also be used.
  * An Amazon Fire TV remote.
  * Common third party RF remotes that are actually keyboards.
  * Most keyboards.
  * IR remotes are *not* supported.
* An HDMI-CEC splice (either a stripped, spliced cable, or a [dedicated board](hw/README.md) and an extra HDMI cable)

## Setup

### HDMI Splice Hardware

Amity splices into the HDMI-CEC bus between the TV, and the receiver using Raspberry Pi GPIO. There are two methods to splice into the HDMI-CEC bus. One method is to strip an existing HDMI cable. The second method is to use [Amity Board](hw/README.md#amity-board), that passes through the HDMI A/V signals without degrading them. Note that all of the commonly available HDMI breakout boards advertised for sale are not designed to pass through high-speed A/V signals, and do not work. Amity installs, by default, for use with a spliced HDMI cable.

[Acquire a board or prepare a cable before proceeding](hw/README.md).

### Initial Installation

Amity setup, and configuration is done entirely in the command terminal, and requires some familiarity with SSH, running terminal commands, and light editing of a configuration file.

It is assumed that the Raspberry Pi will be a dedicated device for home theater control. It may be possible to run Amity with other services on the same Raspberry Pi but it is not supported, and is strongly discouraged.

1. Image Raspberry Pi a 64-bit image **without** Desktop (the 64-bit Lite image) on a MicroSD card. The best tool for this is [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Desktop **MUST NOT** be installed.
2. Insert the MicroSD into the Rpi, power it on, and login with SSH (unless configured differently, the default user created by Raspberry Pi Imager is `pi`. All examples will assume the user is `pi`)
3. Copy the line below, paste it into the terminal, and press enter. This will perform initial configuration of the system, and install Amity. It may take a while. Once complete, there will be a new sub directory named `amity`, i.e. `/home/pi/amity`

    ```commandline
    /bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/retsyx/amity/main/setup_amity)"
    ```

Amity requires a Linux kernel compiled with `cec-gpio` support enabled. If the running kernel doesn't support `cec-gpio` (it likely doesn't), then Amity will download, and install an appropriate pre-compiled kernel, and then reboot. If the running kernel already supports `cec-gpio`, Amity will not replace it.

### Amity Board Configuration

If using a spliced HDMI cable, skip this step.

If using Amity Board, then in the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Reconfigure the GPIO pins to disable the builtin Raspberry Pi pullup resistors:

```commandline
./configure_gpio external
```

And reboot:

```commandline
sudo reboot now
```

### Pairing a Siri Remote or a BLE Keyboard Remote

The preferred method of control is a Siri Remote or a keyboard BLE streamer remote (easier pairing, and great battery life!). The remote **MUST** be unpaired from any other device. If the remote is paired to another device, like an Apple TV, or Mac, it will fail to work with Amity in unpredictable ways. Ensure the remote is charged.

In the terminal, ensure you are in the Amity directory:

```commandline
cd ~/amity
```

Then, to pair the remote, enter:

```commandline
./pair_remote
```

Hold the remote near the Raspberry Pi.

On a Siri Remote, simultaneously press the Menu/Back and the Volume Up (+) buttons for a couple seconds.

On an Amazon Fire remote, press and hold the home button until an orange LED flashes. This may require a couple attempts.

Follow the prompts.

If successful, then the remote has been paired, and is ready for use. In addition, Amity's `config.yaml` file was updated. More about `config.yaml` in the [HDMI Configuration](#hdmi-configuration) section.

### Using a Keyboard for Control

Some media remotes (Amazon Fire, or common third party RF remotes) operate as keyboards. Amity can be controlled with these remotes after they have been installed or paired to the Raspberry Pi. Bluetooth remotes, like Amazon Fire, are [paired just like Siri Remotes](#pairing-a-siri-remote-or-a-ble-keyboard-remote). For generic RF remotes, that typically come with a USB dongle, plug in the dongle. Amazon Fire remotes are recommended as they are typically cheaper, and operate in well defined ways. Generic remotes can be peculiar, and may not work for arbitrary reasons. For example, some remotes have a power button that doesn't generate a key press.

IR remotes are *not* supported.

This document uses the Siri remote as an example, but remote operation is similar in all cases. In particular, Amity uses the direction buttons for activity selection. Amazon Fire activity buttons are undocumented, and are not supported.

### HDMI Configuration

Amity uses a concept of activities to organize the different uses of a home theater system, similar to Harmony remotes. Every activity has a source device (i.e. Apple TV, or PlayStation), an audio output device (i.e. a receiver, or TV for volume commands), an HDMI input switching device (i.e. a receiver), and a display (typically a TV). Amity supports up to 5 activities (because that is the number of buttons available on Siri remotes).

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

At the top is an `adapters` section with the Linux kernel cec-gpio devices Amity discovered. The `front` adapter is connected to the TV, the `back` adapter is connected to the receiver.

After is a `remote` section with the mac address of the paired remote. Below is the `activities` section with the activities that Amity guessed. The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities. More on this in the [usage](#usage) topic.

Let's look at one activity in detail:


```yaml
- name: Watch Living Room
  display: TV
  source: Living Room
  audio: AVR-X3400H
```

The fields are:

* `name` - this can be any descriptive name you choose.
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

After this command Amity will run.

Note that after startup, it may take a few button presses on the remote to establish the connection.

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

After an activity has been selected, the Amity transitions into the active mode.

### Active

When active, all the buttons should behave as expected for the selected activity. For example, when using a PlayStation, the directional buttons navigate the PlayStation interface, select selects, back/menu backs out, and volume controls control the audio device. Touchpad swipes can also be used. This is especially important for Gen 1 remotes without directional buttons.

On a Gen 2, or later, remote press the power button to end the activity and put the system in standby. On Gen 1 remotes, triple tap (not press) on the touchpad to signal a power button press to end the activity, and put the system in standby.

On a Gen 2, or later, remote press the power button, and one of the activity selection buttons (select, and directional) at the same time, to jump directly from one activity to another, without putting the system in standby.

## Strange Devices

HDMI-CEC devices can behave strangely. Here are some known workarounds.

### Nintendo Switch

The Nintendo switch has a minimal HDMI-CEC implementation that appears to be nearly always dormant and ignores practically every command except standby. The Switch only appears when it is powered on directly by the user, or placed in the cradle, and then it automatically requests to be displayed.

As a result, the Switch will often not show up in bus scans, or be auto-configured. The solution is to edit `config.yaml` manually to add an activity for the Switch. When active, the Switch defaults to calling itself `NintendoSwitch`, so an example activity configuration for a Switch would be:

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

Amity can be integrated with HomeKit as a TV accessory. This allows controlling Amity with Siri, and integrating Amity into HomeKit automations. In addition, if using a Siri Remote, remote battery level, and low battery warnings are reported to HomeKit.

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
