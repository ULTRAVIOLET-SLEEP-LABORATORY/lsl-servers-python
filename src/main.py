from drivers.driver import Device
import time

def main():
    device_config = "/home/joshua/src/ULTRAVIOLET-SLEEP-LABORATORY/lsl-servers-python/configs/sample_config.yaml"
    device = Device(device_config)
    

    device.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        device.stop()


if __name__ == "__main__":
    main()