import sys

from remote import SiriRemote, RemoteListener

import gestures

class Callback(RemoteListener):
    def __init__(self):
        self.motion_enabled = False
        self.swipe_recognizer = gestures.SwipeRecognizer((5, 5), self.swipe_callback)

    def event_battery(self, remote, percent: int):
        print("Battery", percent)

    def event_power(self, remote, charging: bool):
        print("Charging", charging)

    def event_button(self, remote, button: int):
        print(f"Button {button:04X}")
        if button & remote.profile.buttons.PLAY_PAUSE:
            if remote.has_motion():
                self.motion_enabled = not self.motion_enabled
                remote.enable_motion(self.motion_enabled)

    def event_touches(self, remote, touches):
        print(f"Touch {touches}")
        self.swipe_recognizer.touches(remote, touches)

    def event_motion(self, remote, motion):
        print(f"Motion {motion}")

    def event_audio(self, remote, data):
        print("Audio", data)

    def swipe_callback(self, recognizer, event):
        if event.type & gestures.EventType.Detected:
            s = ''
            if event.x < 0:
                s = 'LEFT'
            elif event.x > 0:
                s = 'RIGHT'
            elif event.y > 0:
                s = 'UP'
            elif event.y < 0:
                s = 'DOWN'
            print(f'Gesture {s}')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        mac = sys.argv[1]
        SiriRemote(mac, Callback())
    else:
        print("error: no mac address")

