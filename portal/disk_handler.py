from helpers.lvm2.entities import Disk
import requests


class DiskFinder(object):

    @staticmethod
    def get_disk_to_mount():
        response = requests.get("http://10.219.241.250:8000/api/logical_units/?status=modified")
        if not response or response.status_code != requests.codes.ok:
            return None
        logical_unit = response.json()[0]
        response = requests.get(logical_unit["url"]+"get_mount_device_path/")
        if not response:
            return None
        response = response.json()
        if response["result"]:
            return response["device_path"]
        return None


class DiskProcessor(object):

    def __init__(self, disk):
        self._disk = disk

    def start(self, mount_location):
        if self._disk.mount(mount_location):
            x = input("Enter something:")
            self._disk.unmount(mount_location)


if __name__== "__main__":
    disk_path = DiskFinder().get_disk_to_mount()
    if disk_path:
        disk_processor = DiskProcessor(Disk(disk_path))
        disk_processor.start("/mnt")
