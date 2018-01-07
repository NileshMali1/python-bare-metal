import os
import re
from lvm2.helper import Helper
from lvm2.logical_volume import LogicalVolume


class Snapshot(LogicalVolume):
    """A snapshot object for logical volume"""

    def __init__(self, snapshot_volume_path):
        LogicalVolume.__init__(self, snapshot_volume_path)

    def get_parent(self):
        result = self._filter_info("LV snapshot status")
        if result:
            matcher = re.search(r"active destination for ([a-zA-Z0-9]+)", result)
            if matcher:
                return LogicalVolume(self._volume_path.replace(self.get_name(), matcher.group(1)))
        return None

    def recreate(self, snapshot_name, lv_path, size=5.0, unit = "GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", lv_path, "--size", str(size)+unit]
        output = Helper.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            self._volume_path = lv_path.replace(os.path.basename(lv_path), snapshot_name)
            return True
        return False

    def revert(self):
        snap_name = self.get_name()
        parent = self.get_parent()
        (size, unit) = self.get_size()
        if self.remove():
            if self.recreate(snap_name, parent.get_path(), size, unit):
                return True
        return False

    def get_size(self):
        return self._filter_info("COW-table size").split(" ")
