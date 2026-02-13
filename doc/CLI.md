# Amity CLI

Amity can also be managed from the command line. This requires some familiarity with SSH, running terminal commands, and light editing of a configuration file.
Read the [README](../README.md) for an overview of Amity and its functionality.

## Initial Installation

Follow all the steps in [README](../README.md#initial-installation) to install Amity on a Raspberry Pi.
**Ensure to create a user in the web interface to secure it.**

Using the `pi` user password or the SSH private key, SSH into the Amity Raspberry Pi.

## CLI Commands and Editing the Configuration

All commands must be run in the Amity home directory. To make sure you are in the Amity home directory, type:

```commandline
cd ~/amity
```

### HDMI Splice Configuration

If using an Amity Board, use:

```commandline
./configure_gpio external
```

If using a spliced HDMI cable, use:

```commandline
./configure_gpio internal
```

### Ensure Amity is Not Running

Before running any commands, ensure that Amity is not running:

```commandline
./configure_amity disable
```

### Pairing a Siri Remote or a BLE Keyboard Remote

```commandline
./pair_remote
```

### HDMI Configuration

Configuring activities is fairly straightforward thanks to HDMI-CEC.

#### Quick Sanity Scan

Ensure that all home theater devices have HDMI-CEC enabled, and are discoverable. To list all the devices available on HDMI-CEC, run:

```commandline
./configure_hdmi scan
```

If no devices are listed, check the HDMI connection.

#### Automatic Activity Recommendation

Now that all the devices are accounted for, Amity can generate a set of recommended activities:

```commandline
./configure_hdmi recommend
```

The activity configuration is written into `~/amity/var/config/config.yaml`. Open `config.yaml` with your favorite text editor.

#### Editing `config.yaml`

This is an example `config.yaml` with two activities:

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

At the top is an `adapters` section with the Linux kernel HDMI-CEC devices Amity discovered. The `front` adapter is connected to the TV, the `back` adapter is connected to the receiver.

After is a `remote` section with the mac address of the paired remote. Below is the `activities` section with the activities that Amity guessed. The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities.

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

Amity configured an activity with a source device called 'Living Room', using the TV as a display, and the audio receiver for audio output. 'Living Room' is the OSD name of the Apple TV in the living room. The name of the activity can be changed to 'Watch TV' for convenience. The activity name is used with [HomeKit](#enabling-homekit).

And that's it... Amity is now fully configured with a paired remote, and two activities for watching Apple TV, and playing with a PlayStation 5. Let's start it!

## Starting Amity

To start Amity, type:

```commandline
./configure_amity enable
```

Note that after startup, it may take a few button presses on the remote to establish a connection.

## Stopping Amity

To change configuration, or to pair a different remote, Amity must be stopped. To stop Amity, and to prevent it from starting at every system start, type:

```commandline
./configure_amity disable
```

## HomeKit

### Enabling HomeKit

Enabling HomeKit (if not already enabled) will restart Amity.

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

```commandline
./configure_homekit disable
```

### Resetting HomeKit Configuration

This will reset Amity's HomeKit state, and restart Amity, if necessary. To re-add Amity, you will need to remove Amity in the iOS Home app, and add it again as a new accessory.

```commandline
./configure_homekit reset
```

If HomeKit support is still enabled, then the new QR code and setup code required to add Amity into your home will be displayed.

## Home Assistant / MQTT

### Testing MQTT Connection Parameters

Test MQTT connection settings and credentials with the 'test' command.

```
./configure_mqtt test --username <user> --password <pass> --host <host>
```

### Configuring MQTT

Configure MQTT credentials with the 'set-credentials' command. This will restart Amity.

```
./configure_mqtt set-credentials --username <user> --password <pass>
```

Configure MQTT broker connection settings (like host, and port) with the 'set-config' command. This will restart Amity.

```
./configure_mqtt set-config --host <host>
```

### Enabling MQTT

Enabling MQTT (if not already enabled) will restart Amity.

```
./configure_mqtt enable
```

### Disabling MQTT

Disabling MQTT (if not already disabled) will restart Amity.

```
./configure_mqtt disable
```

## License

Amity source code is licensed under the [GPLv3](../LICENSE).