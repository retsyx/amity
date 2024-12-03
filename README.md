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
* A MicroSD card (4GB or larger).
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

It is assumed that the Raspberry Pi will be a dedicated device for home theater control. It may be possible to run other services on the same Raspberry Pi but it is not supported, and is strongly discouraged.

1. Download the latest [Amity image](https://github.com/retsyx/amity/releases/latest/download/amity.img.gz).
2. Using [Raspberry Pi Imager](https://www.raspberrypi.com/software/), write the image to a MicroSD card.
    1. For 'Operating System', select 'Use custom', and select the Amity image.
    2. When prompted to 'Use OS customization', select 'Yes'.
    3. Set the hostname to something memorable, for example `amity`.
    4. Select 'Set username and password' and set the password. The username **must** be `pi`.
      * For advanced users:
        * It is possible to not select 'Set username and password', and instead to enable SSH in the 'Services' tab and to specify a public SSH key.
        * It is also possible to set neither a password, nor enable SSH. However, at this time, this completely precludes upgrading Amity to newer versions. An upgrade will require backing up the config, reinstalling Amity from scratch, and restoring the config.
    5. If using WiFi, set your WiFi network information in the 'Configure Wireless LAN' section
3. Insert the imaged MicroSD into the Raspberry Pi, and wait for it to to complete its initial boot sequence. This may take a few minutes, and a few reboots.
4. In your web browser open the Amity administration page. For example, if the hostname in Raspberry Pi Imager was configured as `amity`, then browse to `https://amity.local` (on Mac) or `https://amity` (on Windows).
 * The web browser will prompt that the site may be unsafe. This is because Amity creates a self signed security certificate for encryption. It is safe. Click on the details, and accept that the site is safe.
5. Create the Amity administration user by entering a username and password. These can be anything.
6. Login with the newly created user.

### Amity Board Configuration

If using a spliced HDMI cable, skip this step.

If using Amity Board, then select the 'Advanced' tab. In the 'HDMI Splice' section press the 'Use with Amity Board' button. When done, The status line should read 'Configured for Amity Board'.

### Pairing a Siri Remote or a BLE Keyboard Remote

The preferred method of control is a Siri Remote or a keyboard BLE streamer remote (easier pairing, and great battery life!). The remote **MUST** be unpaired from any other device. If the remote is paired to another device, like an Apple TV, or Mac, it will fail to work with Amity in unpredictable ways. Ensure the remote is charged.

Select the 'Remotes' tab. The 'Remotes' panel shows if a remote or keyboard is paired, and allows pairing. Press the 'Pair' button. Wait for the initial prompt to start the pairing process on the remote.

Hold the remote near the Raspberry Pi.

On a Siri Remote, simultaneously press the Menu/Back and the Volume Up (+) buttons for a couple seconds.

On an Amazon Fire remote, press and hold the home button until an orange LED flashes. This may require a couple attempts.

Follow the prompts.

If successful, the remote has been paired, and is ready for use.

### Using a Keyboard for Control

Some media remotes (Amazon Fire, or common third party RF remotes) operate as keyboards. Amity can be controlled with these remotes after they have been installed or paired to the Raspberry Pi. Bluetooth remotes, like Amazon Fire, are [paired just like Siri Remotes](#pairing-a-siri-remote-or-a-ble-keyboard-remote). For generic RF remotes, that typically come with a USB dongle, plug in the dongle. Amazon Fire remotes are recommended as they are typically cheaper, and operate in well defined ways. Generic remotes can be peculiar, and may not work for arbitrary reasons. For example, some remotes have a power button that doesn't generate a key press.

IR remotes are *not* supported.

This document uses the Siri remote as an example, but remote operation is similar in all cases. In particular, Amity uses the direction buttons for activity selection. Amazon Fire activity buttons are undocumented, and are not supported.

### HDMI Configuration

Amity uses a concept of activities to organize the different uses of a home theater system, similar to Harmony remotes. Every activity has a source device (i.e. Apple TV, or PlayStation), an audio output device (i.e. a receiver, or TV for volume commands), and a display (typically a TV). Amity supports up to 5 activities (because that is the number of buttons available on Siri remotes).

Configuring activities is fairly straightforward thanks to HDMI-CEC.

Ensure that all home theater devices have HDMI-CEC enabled, and are discoverable. Select the 'Activities' tab, and press the 'Scan HDMI' button to list all the devices available on HDMI-CEC, and to create a recommended list of activities.

Press 'Save' to save the activities.

The names of the devices are their HDMI On Screen Display (OSD) names, and are used to reference the devices in Amity configuration. Ensure that no two devices share the same name. Duplicate names are not supported, and will lead to confusion, failure, and disappointment.

Devices that don't appear in the list don't have HDMI-CEC enabled or have a very broken HDMI-CEC implementation (i.e. Nintendo Switch) that may only partially work in general.

If no devices are listed, ensure the HDMI-CEC splice is correctly attached, and that the HDMI cables are connected.

#### Editing the List of Activities

The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities. The assigned activity button on the remote is pictured next to the activity name. Read the [usage](#usage) topic to learn more. To re-order activities, press the up or down arrow buttons. To remove an activity, press the 'trash' button for that activity. To add a new activity, press the '+' button at the top of the activity list.

#### Editing an Activity

To edit an activity, press the 'Edit' button of the activity.

The fields of an activity are:

* `Name` - this can be any descriptive name you choose. The activity name is used with [HomeKit](#homekit).
* `Display` - the HDMI OSD name of the display device. Typically a TV.
* `Source` - the HDMI OSD name of the AV source device.
* `Audio` - the HDMI OSD name of the audio output device, typically a receiver.
* `Switch Device` (optional) - See [Strange Devices](#strange-devices)
* `Input` (if 'Switch Device' is specified)

Remember to 'Save' the activities when done.

## Usage

Amity has two basic modes, standby, when the home theater is in standby, and active when an activity has been selected.

### Standby

In standby, 1 of 5 activities can be started. On a Gen 2 remote, the 5 activities are assigned to the select, and directional buttons - select, up, right, down, left. Note the order listed here matches the order of activities as specified in Activities configuration tab. The select button starts the first activity, up the second, right the third, and so on. On a Gen 1 remote, there are no directional keys. Instead, press the touchpad (making a click) on the part of the touchpad that corresponds to the direction. Press the center for the first activity, towards the top of the touchpad for the second activity, towards the right for the third activity, and so on.

On a Gen 2 remote, pressing the power button will send a standby signal to all devices. This is useful, if a device is on when it shouldn't be. Gen 1 remotes don't have a power button. Instead, use a triple tap (not press) on the touchpad to signal a power button press.

After an activity has been selected, Amity transitions into the active mode.

### Active

When active, all the buttons should behave as expected for the selected activity. For example, when using a PlayStation, the directional buttons navigate the PlayStation interface, select selects, back/menu backs out, and volume controls control the audio device. Touchpad swipes can also be used. This is especially important for Gen 1 remotes without directional buttons.

On a Gen 2, or later, remote press the power button to end the activity and put the system in standby. On Gen 1 remotes, triple tap (not press) on the touchpad to signal a power button press to end the activity, and put the system in standby.

On a Gen 2, or later, remote press the power button, and one of the activity selection buttons (select, and directional) at the same time, to jump directly from one activity to another, without putting the system in standby.

## Strange Devices

HDMI-CEC devices can behave strangely. Here are some known workarounds.

### Nintendo Switch

The Nintendo switch has a minimal HDMI-CEC implementation that appears to be nearly always dormant and ignores practically every command except standby. The Switch only appears when it is powered on directly by the user, or placed in the cradle, and then it automatically requests to be displayed.

As a result, the Switch will often not show up in bus scans, or be auto-configured. The solution is to create a new activity for the Nintendo Switch:

1. Press the '+' button to create a new activity.
2. Write in the activity name, for example `Play Switch`
3. Select the appropriate Display, and Audio devices.
4. Enter `NintendoSwitch` in the `Source` device field.
5. Press 'OK', and then press 'Save'.

Then to play, turn on the Switch, and select the `Play Switch` activity on the Siri remote. Amity will do the right thing when the Switch is woken up, and announces itself. To end the activity, press the power button on the Siri remote to place the entire system in standby, including the Switch, which will go dormant again.

Sometimes, however, this may not be enough, and the Switch may still not announce its presence. For this case, if the receiver supports selecting inputs over HDMI-CEC, Amity can be configured to select the input on the receiver.

1. Pressing the 'Edit' button of the `Play Switch` activity.
2. Select the receiver as the `Switch Device`.
3. Specify the `Input` number.

This functionality depends on the AVR supporting the feature, and on finding the correct value for the input. Finding the input number is through trial, and error, at the moment. On a Denon AVR-X3400H the numeric input values correspond to the named inputs as follows:

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

Select the 'HomeKit' tab, and press 'Enable'. Follow the instructions to pair Amity with HomeKit.

## Backup & Restore

For backup, Amity configuration can be downloaded in the 'Configuration' section of the  'Advanced' tab. To restore a backup, use the upload feature.

## CLI Management

Amity can also be [managed through the terminal](CLI.md).

## License

Amity source code is licensed under the [GPLv3](LICENSE).
