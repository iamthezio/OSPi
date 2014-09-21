__author__ = 'Rimco'

from options import options


class Station(object):
    SAVE_EXCLUDE = ['SAVE_EXCLUDE', 'index', 'active']

    def __init__(self, stations_instance, index):
        self._stations = stations_instance
        self.activate_master = False

        self.name = "Station %02d" % (index+1)
        self.enabled = False
        self.ignore_rain = False

        options.load(self, index)

    @property
    def index(self):
        return self._stations.get().index(self)

    @property
    def is_master(self):
        return self.index == self._stations.master

    @is_master.setter
    def is_master(self, value):
        if value:
            self._stations.master = self.index
        elif self.is_master:
            self._stations.master = None

    @property
    def active(self):
        return self._stations.active(self.index)

    @active.setter
    def active(self, value):
        if value:
            self._stations.activate(self.index)
        else:
            self._stations.deactivate(self.index)

    def __setattr__(self, key, value):
        try:
            super(Station, self).__setattr__(key, value)
            if not key.startswith('_') and key not in self.SAVE_EXCLUDE:
                options.save(self, self.index)
        except ValueError:  # No index available yet
            pass


class BaseStations(object):
    def __init__(self, count):
        self.master = None
        self._stations = []
        self._state = [False] * count
        for i in range(count):
            self._stations.append(Station(self, i))
        self.clear()

    def resize(self, count):
        while len(self._stations) < count:
            self._stations.append(Station(self, len(self._stations)))
            self._state.append(False)

        # Make sure we turn them off before they become unreachable
        if len(self._stations) > count:
            self.clear()

        while len(self._stations) > count:
            del self._stations[-1]
            del self._state[-1]

    def count(self):
        return len(self._stations)

    def get(self, index=None):
        if index is None:
            result = self._stations[:]
        else:
            result = self._stations[index]
        return result

    def activate(self, index):
        self._state[index] = True

    def deactivate(self, index):
        self._state[index] = False

    def active(self, index=None):
        if index is None:
            result = self._state[:]
        else:
            result = self._state[index]
        return result

    def clear(self):
        for i in range(len(self._state)):
            self._state[i] = False


class DummyStations(BaseStations):
    def resize(self, count):
        super(DummyStations, self).resize(count)
        print "Output count =", count

    def activate(self, index):
        super(DummyStations, self).activate(index)
        print "Activated output", index

    def deactivate(self, index):
        super(DummyStations, self).deactivate(index)
        print "Deactivated output", index

    def clear(self):
        super(DummyStations, self).clear()
        print "Cleared all outputs"


class ShiftStations(BaseStations):
    def __init__(self, count):
        self._io = None
        self._sr_dat = 0
        self._sr_clk = 0
        self._sr_noe = 0
        self._sr_lat = 0

        self._io.setup(self._sr_noe, self._io.OUT)
        self._io.output(self._sr_noe, self._io.HIGH)
        self._io.setup(self._sr_clk, self._io.OUT)
        self._io.output(self._sr_clk, self._io.LOW)
        self._io.setup(self._sr_dat, self._io.OUT)
        self._io.output(self._sr_dat, self._io.LOW)
        self._io.setup(self._sr_lat, self._io.OUT)
        self._io.output(self._sr_lat, self._io.LOW)

        super(ShiftStations, self).__init__(count)

    def _activate(self):
        """Set the state of each output pin on the shift register from the internal state."""
        self._io.output(self._sr_noe, self._io.HIGH)
        self._io.output(self._sr_clk, self._io.LOW)
        self._io.output(self._sr_lat, self._io.LOW)
        for state in reversed(self._state):
            self._io.output(self._sr_clk, self._io.LOW)
            self._io.output(self._sr_dat, self._io.HIGH if state else self._io.LOW)
            self._io.output(self._sr_clk, self._io.HIGH)
        self._io.output(self._sr_lat, self._io.HIGH)
        self._io.output(self._sr_noe, self._io.LOW)

    def resize(self, count):
        super(ShiftStations, self).resize(count)
        self._activate()

    def activate(self, index):
        super(ShiftStations, self).activate(index)
        self._activate()

    def deactivate(self, index):
        super(ShiftStations, self).deactivate(index)
        self._activate()

    def clear(self):
        super(ShiftStations, self).clear()
        self._activate()


class RPiStations(ShiftStations):
    def __init__(self, count):
        import RPi.GPIO as GPIO  # RPi hardware

        self._io = GPIO
        self._io.setwarnings(False)
        self._io.cleanup()
        self._io.setmode(self._io.BOARD)  # IO channels are identified by header connector pin numbers. Pin numbers are always the same regardless of Raspberry Pi board revision.

        self._sr_dat = 13
        self._sr_clk = 7
        self._sr_noe = 11
        self._sr_lat = 15

        super(RPiStations, self).__init__(count)


class BBBStations(ShiftStations):
    def __init__(self, count):
        import Adafruit_BBIO.GPIO as GPIO  # Beagle Bone Black hardware

        self._io = GPIO
        self._io.setwarnings(False)
        self._io.cleanup()

        self._sr_dat = "P9_11"
        self._sr_clk = "P9_13"
        self._sr_noe = "P9_14"
        self._sr_lat = "P9_12"

        super(BBBStations, self).__init__(count)


try:
    stations = RPiStations(options.output_count)
except Exception:
    try:
        stations = BBBStations(options.output_count)
    except Exception:
        stations = DummyStations(options.output_count)