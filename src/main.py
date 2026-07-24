from drivers.meower_driver import MeowerLSLDriver
import time

def main():
    device_config = "/home/joshua/src/ULTRAVIOLET-SLEEP-LABORATORY/lsl-servers-python/configs/meower_config.yaml"
    device = MeowerLSLDriver(device_config)
    

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