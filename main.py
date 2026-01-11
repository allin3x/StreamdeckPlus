import usb.core, usb.util, sys, time
import pulsectl

# --------------------------------------------------------------------
# USB constants - change these if your device shows a different EP/iface
VID = 0x0FD9  # StreamDeck Plus vendor ID
PID = 0x0084  # product ID
IFACE = 0  # interface that reports the knobs
IN_EP = 0x81  # IN endpoint (you can double‑check with lsusb)
# --------------------------------------------------------------------


# PulseAudio / PipeWire helper --------------------------------------------------
class VolumeController:
    """A tiny wrapper around pulsectl that keeps a sink reference."""

    def __init__(self):
        self.pulse = pulsectl.Pulse("streamdeck-volume")
        self.sink = self._get_default_sink()

    def _get_default_sink(self):
        # The first sink is usually the default one
        sinks = self.pulse.sink_list()
        if not sinks:
            raise RuntimeError("No audio sinks found")
        return sinks[0]

    @property
    def current(self) -> float:
        """Return current volume as a float 0-1."""
        # PulseAudio stores per-channel values; we just use the first one.
        return self.sink.volume.value_flat

    def set_relative(self, delta: int):
        """
        Apply *delta* clicks to the sink.
        One click ≈ 1 % of the full range (0-100 %). You can tweak STEP if you
        want a finer or coarser response.
        """
        STEP = 0.01  # 1 % per click

        new_vol = max(0.0, min(1.0, self.current + delta * STEP))
        vol_info = pulsectl.PulseVolumeInfo([new_vol] * len(self.sink.channel_list))
        self.pulse.volume_set_sink_volume(self.sink.index, vol_info)
        # For debugging - print the new percentage
        print(f"  → volume: {int(new_vol * 100)} %")


def find_and_open():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    print(f"dev: {dev}")
    if dev is None:
        raise RuntimeError("StreamDeck not found")

    if dev.is_kernel_driver_active(IFACE):
        print(f"Kernel Driver Active - Detaching")
        dev.detach_kernel_driver(IFACE)

    print("Select the only configuration (value 1 on this device)")
    # dev.set_configuration(1)
    print("Claim the interface")
    usb.util.claim_interface(dev, IFACE)
    return dev


def find_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit("StreamDeck device not found")
    return dev


def open_device(dev):
    """Return a ready-to-use device object."""
    # dev = usb.core.find(idVendor=VID, idProduct=PID)
    # if dev is None:
    # raise SystemExit("Device not found")

    # Make sure no kernel driver owns it
    if dev.is_kernel_driver_active(IFACE):
        try:
            dev.detach_kernel_driver(IFACE)
        except usb.core.USBError as e:
            print(f"Warning: could not detach kernel driver: {e}")

    # Select the only configuration (value 1 on this device)
    dev.set_configuration(1)

    # Claim the interface
    usb.util.claim_interface(dev, IFACE)


def close_device(dev):
    """Release the interface and cleanup."""
    try:
        usb.util.release_interface(dev, IFACE)
    except Exception:
        pass  # ignore errors on release


def bytes_to_hex_str(data):
    """Return a string like '01 03 05 00 ...'."""
    return " ".join(f"{b:02X}" for b in data)


def main():
    # dev = find_device()
    # open_device(dev)

    dev = find_and_open()
    # Map each knob to a VolumeController instance.
    vol_ctrl_knob1 = VolumeController()  # master
    vol_ctrl_knob2 = VolumeController()  # second knob (same sink for demo)

    raw = ""
    hex_str = ""
    print(f"Listening on IN EP {hex(IN_EP)} (press Ctrl-C to stop)")
    try:
        while True:
            try:
                raw = dev.read(IN_EP, 512, timeout=200)
                # Convert to a nice hex string
                hex_str = bytes_to_hex_str(raw)

            except usb.core.USBError as e:
                if e.errno == 110:
                    pass
                elif e.errno == 2:
                    print("\nInterface went away, re-opening…")
                    usb.util.release_interface(dev, IFACE)
                    open_device(dev)

            print(f"Hex String: {hex_str}")

            # Volume Knob 1 turned up
            if "01 03 05 00 01 01" in hex_str:
                # vol_ctrl_knob1.set_relative(1)
                print(f"Volume Knob 1 Turned Up")
            # Volume Knob 1 turned down

            if "01 00 08 00 01" in hex_str:
                print(f"Button Pressed.")

            time.sleep(0.50)
            hex_str = ""

    except KeyboardInterrupt:
        print("\nStopping …")
    finally:
        close_device(dev)


if __name__ == "__main__":
    main()
