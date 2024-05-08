# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import math, time

from remote import HwRevisions

class EventType(object):
    Inactive = 0
    Running = 1
    Begin = 2
    Detected = 4
    End = 8
    Cancelled = 16

class TouchState(object):
    def __init__(self, start_touch):
        self.start_touch = start_touch
        self.last_active_touch = start_touch
    def is_begin_touch(self, touch):
        return self.start_touch.timestamp == touch.timestamp

class GestureRecognizer(object):
    def __init__(self, max_touches, callback):
        self.touch_states = {}
        self.max_touches = max_touches
        self.callback = callback

    def reset(self):
        self.touch_states = {}

    def state_for_touch(self, touch):
        et = 0
        touch_state = self.touch_states.get(touch.id)
        if touch_state is None:
            if len(self.touch_states) == self.max_touches:
                return None, et
            touch_state = TouchState(touch)
            et |= EventType.Begin
            self.touch_states[touch.id] = touch_state
        if touch.p == 0: # Touch is over
            del self.touch_states[touch.id]
            et |= EventType.End
        return touch_state, et

    def last_active_touches(self):
        return [ts.last_active_touch for ts in self.touch_states.values()]

    def touches(self, remote, event):
        return None

class SwipeEvent(object):
    def __init__(self, type, xy):
        self.type = type
        self.x, self.y = xy
    def __str__(self):
        return f'0x{self.type:02X} ({self.x}, {self.y})'

class OneAxisSwipeRecognizer(GestureRecognizer):
    def __init__(self, axis, resolution, callback):
        super().__init__(1, callback) # No multitouch
        self.axis = axis
        self.segments = resolution + 1
    def touches_internal(self, remote, touches):
        event_type = EventType.Running
        counter = 0
        for touch in touches:
            touch_state, et = self.state_for_touch(touch)
            if touch_state is None: # Ignore multitouch
                self.reset()
                return SwipeEvent(EventType.Cancelled, (0, 0))
            event_type |= et
            threshold_distance = remote.profile.touchpad.SIZE_MM // self.segments
            if touch.p > 0:
                axis_distances = touch.axis_distances_from_touch(touch_state.last_active_touch)
                distance = axis_distances[self.axis]
                # Do we have an event?
                if abs(distance) > threshold_distance:
                    counter = int(distance / threshold_distance)
                    touch_state.last_active_touch = touch
                    event_type |= EventType.Detected
            else:
                # If this is a release event, the touch is over.
                # Check for a swipe gesture, and remove the state.
                v = touch.axis_velocities_from_touch(touch_state.start_touch)[self.axis]
                a = -400 # mm/s^2
                if v < 0:
                    a = -a
                t = -v / a
                d = v*t + .5*a*t*t
                counter = int(d / threshold_distance)
                if counter != 0:
                    # Clamp the counter so it doesn't do surprising things...
                    counter = min(max(counter, -6), 6)
                    event_type |= EventType.Detected
        xy = [0, 0]
        xy[self.axis] = counter
        return SwipeEvent(event_type, tuple(xy))

    def touches(self, remote, touches):
        event = self.touches_internal(remote, touches)
        if event is not None:
            self.callback(self, event)


class SwipeRecognizer(object):
    def __init__(self, resolutions, callback):
        self.callback = callback
        self.rs = []
        self.primary_axis = None
        for i in range(2):
            self.rs.append(OneAxisSwipeRecognizer(i, resolutions[i], None))
    def reset(self):
        for r in self.rs:
            r.reset()
    def touches(self, remote, touches):
        # Initially, either axis can generate an event.
        # Once one of the axes generates an event, all further event generation is locked
        # to that axis.
        if self.primary_axis is None:
            for r in self.rs:
                event = r.touches_internal(remote, touches)
                if event.type & EventType.Detected:
                    self.primary_axis = r.axis
                    self.callback(self, event)
                    return
        else:
            event = self.rs[self.primary_axis].touches_internal(remote, touches)
            if event is None: return event
            if event.type & EventType.End:
                self.primary_axis = None
                self.reset()
            self.callback(self, event)
        if self.primary_axis is None:
            event_type = EventType.Inactive
        else:
            event_type = EventType.Running
        self.callback(self, SwipeEvent(event_type, (0, 0)))

class TapEvent(object):
    def __init__(self, type, remote, x, y):
        self.type = type
        self.remote = remote
        self.x = x
        self.y = y

class TapRecognizer(GestureRecognizer):
    def __init__(self, num_fingers, callback):
        super().__init__(num_fingers, callback)
        self.num_fingers = num_fingers
        self.reset()

    def reset(self):
        super().reset()
        self.num_active_touches = 0
        self.have_all_touches = False
        self.end_touches = []
        self.begin_touch_timestamp = None
        self.begin_xy = None

    def midpoint_of_touches(self, touches):
        x = y = 0
        if not touches:
            return x, y
        for touch in touches:
            x += touch.x
            y += touch.y
        x = int(x / len(touches))
        y = int(y / len(touches))
        return x, y

    def touches(self, remote, touches):
        event_type = EventType.Inactive
        for touch in touches:
            touch_state, et = self.state_for_touch(touch)
            if touch_state is None:
                # Too many touches! Reset our state.
                self.reset()
                self.callback(self, TapEvent(EventType.Cancelled, remote, 0, 0))
                return
            touch_state.last_active_touch = touch
            event_type |= EventType.Running
            if et == EventType.Begin:
                self.num_active_touches += 1
                if self.num_active_touches == 1:
                    self.begin_touch_timestamp = time.time()
                if self.num_active_touches == self.num_fingers:
                    self.begin_xy = self.midpoint_of_touches(self.last_active_touches())
                self.end_touches = []
                if self.num_active_touches == self.num_fingers:
                    self.have_all_touches = True
                    event_type |= EventType.Begin
            if et == EventType.End:
                self.num_active_touches -= 1
                self.end_touches.append(touch)
                if self.num_active_touches == 0:
                    if self.have_all_touches:
                        # Was this more of a long press than a tap?
                        td = time.time() - self.begin_touch_timestamp
                        if td > .4 or td < .05:
                            self.reset()
                            self.callback(self, TapEvent(EventType.Cancelled, remote, 0, 0))
                            return
                        # Is this more a of swipe than a tap?
                        end_xy = self.midpoint_of_touches(self.end_touches)
                        rtp = remote.profile.touchpad
                        dx_mm = (end_xy[0] - self.begin_xy[0]) / rtp.RESOLUTION[0] * rtp.SIZE_MM
                        dy_mm = (end_xy[1] - self.begin_xy[1]) / rtp.RESOLUTION[1] * rtp.SIZE_MM
                        distance_mm_2 = dx_mm*dx_mm + dy_mm*dy_mm
                        if distance_mm_2 > 25:
                            self.reset()
                            self.callback(self, TapEvent(EventType.Cancelled, remote, 0, 0))
                            return

                        event_type &= ~EventType.Running
                        event_type |= EventType.Detected | EventType.End

        if event_type & EventType.Detected:
            xy_touches = self.end_touches
        else:
            xy_touches = self.last_active_touches()
        x, y = self.midpoint_of_touches(xy_touches)
        if event_type & EventType.End:
            self.reset()
        self.callback(self, TapEvent(event_type, remote, x, y))

class MultiTapRecognizer(object):
    def __init__(self, num_fingers, num_taps, callback):
        self.num_fingers = num_fingers
        self.num_taps = num_taps
        self.callback = callback
        self.tap_recognizer = TapRecognizer(self.num_fingers, self.tap_event)
        self.reset()

    def reset(self):
        self.last_tap_time = time.time()
        self.tap_recognizer.reset()
        self.tap_count = 0

    def tap_event(self, recognizer, event):
        if event.type & EventType.Detected:
            now = time.time()
            if now - self.last_tap_time > .4:
                if self.tap_count > 0:
                    self.callback(self, TapEvent(EventType.Cancelled, event.remote, 0, 0))
                    self.tap_count = 0
            self.tap_count += 1
            self.last_tap_time = now
            if self.tap_count == 1:
                if self.num_taps == 1:
                    self.callback(self, event)
                    self.tap_recognizer.reset()
                    return
                else:
                    self.callback(self, TapEvent(EventType.Begin, event.remote, event.x, event.y))
            if self.tap_count == self.num_taps:
                self.callback(self, event)
                self.tap_count = 0

    def touches(self, remote, touches):
        self.tap_recognizer.touches(remote, touches)

# This tweaks button values, in lieu of an event callback
class DPadEmulator(object):
    def __init__(self):
        self.last_touch = None
        self.last_buttons = 0

    def touches(self, remote, touches):
        self.last_touch = touches[0]

    def buttons(self, remote, buttons):
        if remote.profile.hw_revision not in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            return buttons
        if self.last_touch is None:
            return buttons
        pressed = buttons & ~self.last_buttons
        released = self.last_buttons & ~buttons
        self.last_buttons = buttons
        btns = remote.profile.buttons
        if pressed & btns.SELECT:
            zt = remote.zero_touch()
            d_mm = self.last_touch.distance_from_touch(zt)
            if d_mm < 12:
                return buttons
            dx_mm, dy_mm = self.last_touch.axis_distances_from_touch(zt)
            direction = math.degrees(math.atan2(dx_mm, dy_mm)) + 180
            a = 30
            btn = btns.INVALID
            if direction < a or direction > 360 - a:
                btn = btns.DOWN
            elif direction > 90-a and direction < 90+a:
                btn = btns.LEFT
            elif direction > 180-a and direction < 180+a:
                btn = btns.UP
            elif direction > 270-a and direction < 270+a:
                btn = btns.RIGHT
            return (buttons & ~btns.SELECT) | btn
        elif released & btns.SELECT:
            return buttons & ~(btns.DOWN|btns.LEFT|btns.UP|btns.RIGHT)
        return buttons
