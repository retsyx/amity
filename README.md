# Amity
Home theater control over HDMI-CEC with a Siri Remote

* [Introduction](#introduction)
* [Caveats](#caveats)
* [Prerequisites](#prerequisites)
* [Setup](#setup)
  * [Initial Installation](#initial-installation)
  * [Pairing a Siri Remote](#pairing-a-siri-remote)
  * [HDMI Configuration](#hdmi-configuration)
    * [Quick Sanity Scan](#quick-sanity-scan)
    * [Automatic Activity Recommendation](#automatic-activity-recommendation)
    * [Editing config.yaml](#editing-configyaml)
    * [Scanning HDMI Inputs](#scanning-hdmi-inputs)
* [Starting Amity](#starting-amity)
* [Stopping Amity](#stopping-amity)
* [Usage](#usage)
  * [Standby](#standby)
  * [Active](#active)

## Introduction

Use a Raspberry Pi, and a Siri Remote to control a home theater system over HDMI-CEC.

## Caveats

HDMI-CEC is a terrible control protocol. Different equipment manufacturers implement it in often incompatible ways. It often behaves unpredictably, and it can be an endless source of headaches. Using it for anything is a very bad idea. Even more so when it is used in ways unintended by its designers, like Amity uses it.

Testing of Amity has been limited to the equipment I have. It works for me. It may very well not work for you. There may be ways to fix issues you encounter, and there may not. HDMI-CEC is arbitrary, and capricious.

Amity is known to work (with my equipment, anyway) with a traditional setup centered around a receiver. In my case, I have an LG TV connected to a Denon receiver output. I have an Apple TV, PlayStation, and Nintendo Switch (that has a practically non-functioning HDMI-CEC implementation) connected to the receiver's inputs. When I want to change what I'm watching, I change inputs on the receiver.

Amity does not support eArc (an Amity limitation), and may not be able to switch inputs on TVs - my LG TV doesn't respond to input selection HDMI-CEC commands (there may be workarounds, or secret vendor commands, but I haven't found them).

With this in mind, if you are ready to take on HDMI-CEC, you are ready to try Amity.

## Prerequisites

* Gen 2, and later, Siri Remotes require Bluetooth 5.0. As a result, Raspberry Pi 4, or later is required, along with an appropriate power supply. Network access is required for initial setup but not when controlling your home theater.
* An unpaired Siri Remote. Preferably, a Gen 2 or Gen 3 remote (aluminum case with a power button in the top right corner), but a Gen 1 remote (black top) can also work.
* An HDMI cable

## Setup

### Initial Installation

Amity setup, and configuration is done entirely in the command terminal, and requires some familiarity with the terminal.

It is assumed that this will be a dedicated device for home theater control. It may be possible to run Amity with other services on the same RPi but it is strongly discouraged.

1. Image Raspberry Pi **without** Desktop on a MicroSD card. The best tool for this is [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Desktop **MUST NOT** be installed.
2. Insert the MicroSD into the Rpi, power it on, and login via SSH, or hook up a keyboard and mouse, and use the console (unless configured, the default user created by Raspberry Pi Imager is `pi`. All examples will assume the user is `pi`)
3. In the console (or SSH) ensure you are in the `pi` user home directory:

    `cd ~`

4. Copy the line below, paste it into the terminal, and press enter. This will download Amity, install all of Amity's dependencies, create a venv, and do some initial configuration of the system. It may take a while. Once complete, there will be a new sub directory `amity`, i.e. `/home/pi/amity`

    ```
    /bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/retsyx/amity/main/setup_amity)"
    ```

### Pairing a Siri Remote

The remote **MUST** be unpaired from any other device. If the remote is paired to another device, like an Apple TV, or Mac, it will fail to work with Amity in unpredictable ways. Ensure the remote is charged.

In the terminal, ensure you are in the Amity directory:

`cd ~/amity`

Then, to pair the remote, enter:

`./pair_remote`

Hold the remote near the Raspberry Pi and simultaneously press the Menu/Back and the Volume Up (+) buttons for a couple seconds. Follow the prompts.

If successful, then the remote has been paired, and is ready for use. In addition, Amity's `config.yaml` file was updated. More about `config.yaml` in the next section.

### HDMI Configuration

Amity uses a concept of activities to organize the different uses of a home theater system, similar to Harmony remotes. Every activity has a source device (i.e. Apple TV, or PlayStation), an audio output device (i.e. a receiver, or TV for volume commands), an HDMI input switching device (i.e. a receiver, or TV), and a display (typically a TV). Amity supports up to 5 activities (because of the small number of buttons on Siri remotes).

Configuring activities is a bit confusing at first, but once the basics are configured, it's easy to manage.


Plug in Amity's HDMI cable into the receiver! Note that on Raspberry Pi 4, there are two micro HDMI ports. Insert the cable into the port closer to the USB-C power port.

#### Quick Sanity Scan

Ensure that all home theater devices have HDMI-CEC enabled, and are discoverable. To list all the devices available on HDMI-CEC, in the Amity directory, run:

`./configure_hdmi scan`

Pay particular attention to the names of the devices. These are the HDMI On Screen Display (OSD) names of the devices, and are used to reference the devices in Amity configuration.

Devices that don't appear in the list don't have HDMI-CEC enabled or have a very broken HDMI-CEC implementation (i.e. Nintendo Switch) that may only partially work in general.

If you don't see any devices except the Amity device, ensure the HDMI cable is correctly inserted on both ends, and that it is inserted into the micro HDMI port closer to the USB-C power port on the Raspberry Pi.

#### Automatic Activity Recommendation

Now that all the devices are accounted for, Amity can guess a set of activities:

`./configure_hdmi recommend`

The activity configuration was written into `config.yaml` in the Amity directory (i.e. `~/amity/config.yaml`). Open `config.yaml` with your favorite text editor.

#### Editing config.yaml

Here's an example `config.yaml` with two activities:

```yaml
remote:
    mac: 12:34:56:78:9A:BC
activities:
    - name: Watch Living Room
      display: TV
      source: Living Room
      audio: AVR-X3400H
      switch:
        device: AVR-X3400H
        input: <SCAN INPUTS TO FIND ME>
    - name: Play PlayStation 5
      display: TV
      source: PlayStation 5
      audio: AVR-X3400H
      switch:
        device: AVR-X3400H
        input: <SCAN INPUTS TO FIND ME>
```

At the top is a `remote` section with the mac address of the paired remote. Below is the `activities` section with the activities that Amity guessed. The order of the activities matters. Each activity is assigned an activation button on the remote based on its position in the list of activities. More on this in the [usage](#usage) topic.

 Let's look at one activity in detail:


```yaml
- name: Watch Living Room
  display: TV
  source: Living Room
  audio: AVR-X3400H
  switch:
    device: AVR-X3400H
    input: <SCAN INPUTS TO FIND ME>
```

The fields are:

* `name` - this can be anything.
* `display` - the HDMI OSD name of the display device. Typically a TV.
* `source` - the HDMI OSD name of the AV source device.
* `audio` - the HDMI OSD name of the audio output device, typically a receiver.
* `switch` - a device that needs to have its inputs switched.
* `switch device` - the HDMI OSD name of the device to be switched.
* `switch input` - the index of the input to switch to.

Amity configured an activity with a source device called 'Living Room', using the TV as a display, and the audio receiver for audio output, and HDMI input selection. That's pretty good but not complete. First, 'Living Room' is the OSD name of the Apple TV in the living room, so to make it easier to remember, we will change the name of the activity to 'Watch Apple TV'. In addition, instead of an index, the input is `<SCAN INPUTS TO FIND ME>`. So let's scan inputs..

#### Scanning HDMI inputs

Scanning inputs consists of sequentially trying all the inputs on the switch device (i.e. a receiver, or TV) to see what they are connected to. You may need to turn on all the devices to know what each input is, or you can look at the input names on the TV or receiver display. In the example, the switch device is `AVR-X3400H`, a receiver.

Turn on the TV, and receiver, grab a pencil, and paper and enter the scanning command into the terminal:

`./configure_hdmi scan-inputs`

Select the switch device to scan. Typically, this is the receiver. In our example, it is `AVR-X3400H`. Follow the prompts to sequentially try every HDMI input. Use pencil, and paper to write down what is connected to each input index as printed by `scan-inputs`.

In the example, the receiver input for the Apple TV is 5, and for the PlayStation, it is 4. With input in hand, and a preferred activity name, we can now edit `config.yaml` to look like this:

```yaml
remote:
    mac: 12:34:56:78:9A:BC
activities:
    - name: Watch Apple TV
      display: TV
      source: Living Room
      audio: AVR-X3400H
      switch:
        device: AVR-X3400H
        input: 5
    - name: Play PlayStation 5
      display: TV
      source: PlayStation 5
      audio: AVR-X3400H
      switch:
        device: AVR-X3400H
        input: 4
```

Amity is now fully configured with a paired remote, and two activities for watching Apple TV, and playing with a PlayStation 5. Let's start it!

## Starting Amity

To start Amity, type:

```
./setup_amity enable
```

Amity is now running. Now, close the terminal, and start playing with the remote.

## Stopping Amity

To change configuration, or pair a different remote, Amity must be stopped. To stop Amity, and to prevent it from starting at every system start, type:

```
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

## License

Amity source code is licensed under the [GPLv3](LICENSE).