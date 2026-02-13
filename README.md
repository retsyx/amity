# Amity
HDMI-CEC that works!

Control your home theater with a familiar remote, and integrate it with HomeKit or Home Assistant home automation systems.

Read the [rationale](doc/rationale.md), to know why Amity uses HDMI-CEC, and how it works.

## Prerequisites

* A Raspberry Pi 3 Model B+, or Pi Zero 2 W, or newer, that can run 64-bit Linux; with an appropriate power supply. Network connectivity is required for initial setup but not when controlling your home theater.
* A MicroSD card (4GB or larger).
* A remote control. See the [list of supported remotes](doc/supported-remotes.md).
* An [Amity Fin](hw/README.md) and an extra HDMI cable.

## Caveats

### Use Amity at Your Own Risk

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

While Amity has been tested and has worked reliably with some HDMI equipment, there may still be a risk from unknown bugs. Also, when putting together Amity, you may make a mistake - this may destroy your HDMI equipment and/or your Raspberry Pi.

!!! Using Amity may destroy your expensive HDMI equipment. Proceed at your own risk !!!

### Amity is an HDMI-CEC Controller (Not a Universal Remote)

Amity is designed for a traditional setup centered around an audio/video receiver (AVR). For example, a TV connected to a receiver output, and various playback devices (i.e. media streamers, blu-ray players, and game consoles, etc.) connected to the receiver's inputs. When changing the source, the input is changed on the receiver. The HDMI-CEC protocol only allows the designated TV to select sources or devices to declare themselves as active sources. TVs do not heed arbitrary source selection commands from other devices. As a result, Amity cannot select inputs on a TV, and cannot control sources connected directly to a TV, including built-in smart TV apps. Similarly, Amity does not support HDMI ARC/eARC. If you use smart TV apps or connect devices, other than a receiver, directly to the TV inputs, Amity is not for your system.

Amity can only control devices that support HDMI-CEC! However, devices that don't support HDMI-CEC (old game consoles, for example) can still be facilitated.

### Amity is a Proof of Concept

HDMI-CEC is unevenly implemented by different manufacturers, so it doesn't always work as expected. At present, Amity can be considered a proof of concept because of the limited set of equipment it has been tested with. It works for me. It may work flawlessly with your equipment, or it may very well not. There may be ways to fix issues you encounter, and there may not. As more equipment is tested with Amity, its utility will become clearer.

Equipment that is known to be compatible with Amity:

- LG OLED TV
- Denon AVR-X3400H
- Apple TV 4K
- Sony Playstation 4/5
- Amazon Fire TV (media player)
- Nintendo Switch (see [Strange Devices](#strange-devices))
- Wii (see [Non-HDMI Sources](#non-hdmi-sources))

## Setup

### HDMI Hardware

Amity inserts itself into the HDMI-CEC bus between the TV, and the receiver. The preferred method is to use Amity Fin.

[Acquire Amity Fin before proceeding](hw/README.md).

### Initial Installation

It is assumed that the Raspberry Pi will be a dedicated device for home theater control. It may be possible to run other services on the same Raspberry Pi but it is not supported, and is strongly discouraged.

Installation is performed with [Raspberry Pi Imager 2.0](https://www.raspberrypi.com/software/) or later (earlier versions will not work).

1. In Raspberry Pi Imager, press `App Options` (bottom left of the app).
2. In the App Options popup, press `Edit` to edit the Content Repository.
3. In the Content Repository popup, select `Use custom URL` and paste this URL into the text field: `https://github.com/retsyx/amity/releases/latest/download/amity-os.json`
4. Press `Apply & Restart`.
5. Run through the configuration wizard:
    1. Select the Raspberry Pi device you are going to use.
    2. Select the OS - `Amity`.
    3. Select the MicroSD.
    4. Set the hostname to something memorable, for example `amity`.
    5. Optionally, set localisation or leave as is.
    6. Set the username and password. The username **must** be `pi`.
    7. If using WiFi, set WiFi network information.
    8. Optionally, enable SSH, and set credentials. It is recommended to enable SSH.
6. Write the image to the MicroSD card.
7. Insert the imaged MicroSD into the Raspberry Pi, and wait for it to complete its initial boot sequence. This may take a few minutes, and a few reboots.
8. In your web browser open the Amity administration page. For example, if the hostname in Raspberry Pi Imager was configured as `amity`, then browse to `https://amity.local` (on Mac) or `https://amity` (on Windows).
 * The web browser will prompt that the site may be unsafe. This is because Amity creates a self signed security certificate for encryption. It is safe. Click on the details, and accept that the site is safe.
9. Create the Amity administration user by entering a username and password. These can be anything.
10. Login with the newly created user.

### Amity Fin Configuration

If using Amity Fin, select the 'Advanced' tab. In the 'HDMI Splice' section press the 'Use with Amity Board' button. When done, the status line should read 'Configured for Amity Board'.

### HDMI Connections

Amity connects between the TV and the receiver.

1. Disconnect the HDMI cable connecting the TV input to the receiver's output.
2. Use one HDMI cable to connect the TV's input to the Amity Fin HDMI port marked `TV`.
3. Use a second HDMI cable to connect the receiver output to the Amity Fin HDMI port marked `AVR`.

### Pairing a Remote

The remote **MUST** be unpaired from any other device. If the remote is paired to another device, like a streamer or TV, it will fail to work with Amity in unpredictable ways. Pairing and unpairing steps for supported remotes are listed [here](doc/supported-remotes.md). Ensure the remote is charged.

1. Select the 'Remotes' tab. The 'Remotes' panel shows if a remote or keyboard is paired, and allows pairing. Press the 'Pair' button. Wait for the initial prompt to start the pairing process on the remote.

2. Hold the remote near the Raspberry Pi.

3. Start the pairing process on the remote (see pairing steps for supported remotes [here](doc/supported-remotes.md)).

4. Follow the prompts.

If successful, the remote has been paired, and is ready for use.

### Activity Configuration

Amity uses a concept of activities to organize the different uses of a home theater system, similar to Harmony remotes. Every activity has a source device (i.e. Apple TV, or PlayStation), an audio output device (i.e. a receiver, or TV for volume commands), and a display (typically a TV). The remote's directional buttons are used for activity selection (on remotes that have them, the blue, red, green and yellow color buttons are also used for activity selection). This allows for up to 5 activities - 4 direction buttons and the select button.

Configuring activities is fairly straightforward thanks to HDMI-CEC.

Ensure that all home theater devices have HDMI-CEC enabled, and are discoverable. Select the 'Activities' tab, and press the 'Scan HDMI' button to list all the devices available on HDMI-CEC, and to create a recommended list of activities.

Press 'Save' to save the recommended activities.

The names of the devices are their HDMI On Screen Display (OSD) names, and are used to reference the devices in Amity configuration. Ensure that no two devices share the same name. Duplicate names are not supported, and will lead to confusion, failure, and disappointment.

Devices that don't appear in the list don't have HDMI-CEC enabled or have a very broken HDMI-CEC implementation (i.e. Nintendo Switch) that may only partially work in general.

If no devices are listed, ensure that Amity's HDMI ports are correctly attached.

#### Editing the List of Activities

The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities. The assigned activity button (and color button) on the remote is pictured next to the activity name. Read the [usage](#usage) topic to learn more. To re-order activities, press the up or down arrow buttons. To remove an activity, press the 'trash' button for that activity. To add a new activity, press the '+' button at the top of the activity list.

#### Editing an Activity

To edit an activity, press the 'Edit' button of the activity.

The fields of an activity are:

* `Name` - this can be any descriptive name you choose. The activity name is used with [HomeKit](#homekit).
* `Display` - the HDMI OSD name of the display device. Typically a TV.
* `Source` - the HDMI OSD name of the AV source device.
* `Audio` - the HDMI OSD name of the audio output device, typically a receiver.
* `Switch Device` (optional) - See [Strange Devices](#strange-devices)
* `Input` (if `Switch Device` is specified)

Remember to 'Save' the activities when done.

## Usage

Amity has two basic modes, standby, when the home theater is in standby, and active when an activity has been selected.

Note that while Amity supports multi-button and long button presses for additional functionality, the vast majority of users (e.g. family members) can ignore all of it and fully use Amity with simple button presses.

### Standby

In standby, 1 of up to 10 activities can be started. The first 5 activities are assigned to the select, and directional buttons - select, up, right, down, left. Note the order listed here matches the order of activities as specified in the Activities configuration tab. The select button starts the first activity, up the second, right the third, and so on. The next 5 activities are assigned to long presses of the same buttons, in the same order. A long press of the select button starts the sixth activity, a long press of the up button starts the seventh activity, and so on. On remotes with color buttons (blue, red, green, yellow), the color buttons are assigned to the first 4 activities.

A short press of the power button starts the first activity. A long press of the power button sends a standby command to all devices. This is useful, if a device is on when it shouldn't be.

After an activity has been selected, Amity transitions into the active mode.

Check if your remote has idiosyncrasies that may make operation a little different than described in the list of [supported remotes](doc/supported-remotes.md).

### Active

When active, all the buttons should behave as expected for the selected activity. For example, when using a PlayStation, the directional buttons navigate the PlayStation interface, select selects, back/menu backs out, and volume controls control the audio device. On remotes equipped with a touchpad, swipes can also be used.

A short press of the power button ends the activity and puts the system in standby. A long press of the power button refreshes the current activity to ensure all devices are as they should be. This is useful, if a device is not on when it should be.

For remotes that support multiple simultaneous button presses; press the power button, and then one of the activity selection buttons (select, and directional) at the same time, to jump directly from the current activity to one of the other activities, without putting the system in standby.

Check if your remote has idiosyncrasies that may make operation a little different than described in the list of [supported remotes](doc/supported-remotes.md).

## Strange Devices

HDMI-CEC devices can behave strangely. Here are some known workarounds.

### Nintendo Switch

The Nintendo switch has a minimal HDMI-CEC implementation that appears to be nearly always dormant and ignores practically every command except standby. The Switch only appears when it is powered on directly by the user, or placed in the cradle, and then it automatically requests to be displayed.

As a result, the Switch will often not show up in device scans, or be auto-configured. The solution is to create a new activity for the Nintendo Switch:

1. Press the '+' button to create a new activity.
2. Write in the activity name, for example `Play Switch`
3. Select the appropriate Display, and Audio devices.
4. Enter `NintendoSwitch` in the `Source` device field.
5. Press 'OK', and then press 'Save'.

Then to play, turn on the Switch, and select the `Play Switch` activity on the remote. Amity will do the right thing when the Switch is woken up, and announces itself. To end the activity, press the power button on the Siri remote to place the entire system in standby, including the Switch, which will go dormant again.

Sometimes, however, this may not be enough, and the Switch may still not announce its presence. For this case, the Switch can be configured similarly to a [non-HDMI source](#non-hdmi-sources).

## Non-HDMI Sources

Non-HDMI sources can be minimally supported, if the receiver supports input selection over HDMI-CEC. An activity for a non-HDMI source can still control the display and receiver, including power and volume, but cannot control the power of the non-HDMI source or send it menu commands. This limited support is particularly useful for old game consoles that require the use of their own game controllers in any case so a universal remote to control them is of limited value.

To support a non-HDMI source, Amity can be configured to select the input on the receiver. In the activity settings:

1. Select the receiver as the `Switch Device`.
2. Specify the `Input` number.

This functionality depends on the receiver supporting the feature, and on knowing the correct value for the input. On a Denon AVR-X3400H the numeric input values can be configured in the receiver setup menus. From the factory, the numeric input values on a Denon AVR-X3400H correspond to the named inputs as follows:

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

Amity can be integrated with HomeKit as a TV accessory. This allows controlling Amity with Siri, and integrating Amity into HomeKit automations. In addition, if using a BLE remote that supports battery level reporting, the remote battery level, and low battery warnings are reported to HomeKit.

It is highly recommended to complete all activity configuration, and setup before adding Amity into HomeKit.

Select the 'HomeKit' tab, and press 'Enable'. Follow the instructions to pair Amity with HomeKit.

## Home Assistant / MQTT

Amity can be integrated with Home Assistant. This allows integrating Amity into Home Assistant automations.  In addition, if using a BLE remote that supports battery level reporting, the remote battery level and charge state is reported to Home Assistant.

It is highly recommended to complete all activity configuration, and setup before adding Amity into Home Assistant.

While Amity's MQTT implementation is tailored for seamless operation with Home Assistant, it can be used with any MQTT based system.

Select the 'MQTT' tab, configure the required MQTT settings and press 'Enable'.

## Backup & Restore

For backup, Amity configuration can be downloaded in the 'Configuration' section of the 'Advanced' tab. To restore a backup, use the upload feature in the same tab.

## CLI Management

Amity can also be [managed through the terminal](doc/CLI.md).

## License

Amity source code is licensed under the [GPLv3](LICENSE).
