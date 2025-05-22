import asyncio
from bleak import BleakClient, BleakScanner

# Device and characteristic UUIDs
DEVICE_ADDRESS = "69:82:20:D3:DE:C7"
TREADMILL_DATA_UUID = "00002acd-0000-1000-8000-00805f9b34fb"
CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"

async def keep_alive(client):
    """Periodically send a keep-alive command to maintain the connection."""
    while client.is_connected:
        try:
            # Sending a "start/resume" (0x07) command as a keep-alive.
            await client.write_gatt_char(CONTROL_POINT_UUID, bytearray([0x07]), response=True)
            print("Keep-alive command (0x07) sent.")
        except Exception as e:
            print("Error sending keep-alive command:", e)
        await asyncio.sleep(10)  # Adjust the interval as needed.

async def force_connect_loop():
    while True:
        print("Scanning for treadmill device...")
        # Look for the device by its BLE address.
        device = await BleakScanner.find_device_by_address(DEVICE_ADDRESS, timeout=20.0)
        if not device:
            print("Device not found, retrying in 5 seconds...")
            await asyncio.sleep(5)
            continue

        client = BleakClient(device, use_cached_services=False)
        try:
            print("Attempting connection...")
            await client.connect(timeout=30.0)
            print("Connected!")

            # Allow time for the device to initialize its GATT services.
            await asyncio.sleep(3)
            services = await client.get_services()
            service_uuids = [service.uuid for service in services]
            if TREADMILL_DATA_UUID not in service_uuids:
                raise Exception("Treadmill data service not found.")

            # Send an initial control command (here, 0x00 as an example).
            print("Sending initial control command (0x00)...")
            await client.write_gatt_char(CONTROL_POINT_UUID, bytearray([0x00]), response=True)
            print("Initial control command sent.")

            # Start the keep-alive task to mimic periodic interaction.
            keep_alive_task = asyncio.create_task(keep_alive(client))

            print("Entering main loop to keep connection alive...")
            # Keep the connection open until it drops.
            while client.is_connected:
                await asyncio.sleep(1)

            # Cancel the keep-alive task if the connection is lost.
            keep_alive_task.cancel()

        except Exception as e:
            print(f"Connection error: {e}")

        finally:
            if client.is_connected:
                await client.disconnect()
            print("Disconnected. Will retry in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(force_connect_loop())
    except KeyboardInterrupt:
        print("Force-connect script terminated.")
