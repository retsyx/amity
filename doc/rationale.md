# Amity Rationale

## Why?

Since the discontinuation of the Logitech Harmony universal remote, there are no good home theater remotes that are easy to setup, reliable, simple to use by everyone in the family, have a long battery life, and are reasonably priced.

Amity came out of a need to replace an aging Logitech Harmony Hub Smart Control system.

## How?

Remotes like the Siri Remote, the Amazon Fire TV remote, the Samsung SolarCell remote, or the Vizio voice remote are high quality, and readily available. They are simple, robust, last a long time on a charge, are very easy to use by everyone in the family, and there is probably one laying unused in a drawer somewhere. So why not use one to control the home theater?

Raspberry Pis are powerful, flexible, readily available, and cheap enough (especially the Pi Zero 2 W).

Most modern home theater components support HDMI-CEC. HDMI-CEC promises easy home theater control but, due to how it is commonly implemented, fails to deliver on the promise. So let's make HDMI-CEC work the way it should (🤞).

## How Amity Works

### The Problem

The primary problem encountered with HDMI-CEC is that system components can compete to be displayed on the TV. This causes the system to switch back and forth between components in a way that doesn't match the user's intent. This problems stems from HDMI-CEC's protocol design and the inherent ambiguity of discerning the user's intent from disparate parts of the system.

HDMI-CEC allows both the TV to select the component to display, and for any component to request to be displayed. A TV normally selects the component to display based on the user selecting an input with the TV remote. How a component decides to request display is completely up to the component manufacturer. Ideally, when the user picks up a component remote and presses the power button, the component can wake up the system and request to be displayed. This matches user intent. However, some components will request to be displayed when the TV signals over HDMI-CEC that it has powered on. This matches user intent, and saves the user time, if the user turns on the TV with the TV remote and has only one component in the system. However, this logic breaks down if the user has two components. If the user turns on component A with its remote, it powers on the TV, which signals its status, which causes component B to request display, and now the user is presented component B instead of component A.

### Amity

Amity fixes the problem by inserting itself on the HDMI-CEC bus between the TV and the rest of the system and mediating with definitive knowledge of the user's intent. To the TV, Amity behaves as the only component available to the TV. To the rest of the system, Amity behaves as the TV. Amity knows user intent based on the user's selected activity on the remote. It can power on and off the entire system, it can select the correct component to display, and it never sends messages that trigger components to request to display themselves. Finally, if a component requests to be displayed when it shouldn't, Amity can catch the request, override it, and send the component a standby message to get it to stop.

## Cost

Amity can be extremely cheap to put together. An example breakdown of costs:

- Raspberry Pi Zero 2 W with headers - $18
- MicroSD card - $10
- Raspberry Pi power adapter - $10
- A remote - free if you already have a [supported remote](supported-remotes.md) and don't mind losing features like voice commands. Otherwise, ~$20 - $60.
- HDMI cable - $6
- [Amity Fin](../hw/README.md) - ~$16. Boards need to be ordered directly from a PCB manufacturer. PCB manufacturers typically have minimum order counts of a few boards. When ordering 5 boards, the cost per board is ~$16. With larger orders, the cost per board decreases substantially.

The total cost can be up to ~$65 with a low volume manufactured Amity Fin.


