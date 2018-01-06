import os
import re
from lvm2.helper import Helper


class LogicalVolumeSnapshot(object):
    """A snapshot object for logical volume"""

    def __init__(self, snapshot_volume_path):
        self._snapshot_volume_path = snapshot_volume_path

    def get_info(self):
        args = ["lvdisplay", self._snapshot_volume_path]
        output = Helper.exec(args)
        if output:
            return Helper.format(output, "--- Logical volume ---")
        return None

    def _filter_info(self, filter_key=None):
        info = self.get_info()
        if info and filter_key:
            if filter_key in info:
                return info[filter_key]
            else:
                return None
        return info

    def get_parent_name(self):
        result = self._filter_info("LV snapshot status")
        if result:
            matcher = re.search(r"active destination for ([a-zA-Z0-9]+)", result)
            if matcher:
                result = matcher.group(1)
        return result

    def get_name(self):
        return self._filter_info("LV Name")

    def get_path(self):
        return self._filter_info("LV Path")

    def get_size(self):
        return self._filter_info("COW-table size").split(" ")

    def get_volume_group(self):
        return self._filter_info("VG Name")

    def rename(self, new_name):
        old_name = self.get_name()
        vg_name = self.get_volume_group()
        output = Helper.exec(["lvrename", vg_name, old_name, new_name])
        if output and "Renamed \""+old_name+"\" to \""+new_name+"\" in volume group \""+vg_name+"\"":
            self._snapshot_volume_path = self._snapshot_volume_path.replace(old_name, new_name)
            return True
        return False

    def recreate(self, snapshot_name, lv_path, size=5.0, unit = "GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", lv_path, "--size", str(size)+unit]
        output = Helper.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            self._snapshot_volume_path = lv_path.replace(os.path.basename(lv_path), snapshot_name)
            return True
        return False

    def remove(self):
        output = Helper.exec(["lvremove", "--force", self._snapshot_volume_path])
        if output and 'Logical volume "' + os.path.basename(self._snapshot_volume_path) + '" successfully removed' in output:
            self._snapshot_volume_path = None
            return True
        return False

    def revert(self, ):
        snap_name = self.get_name()
        parent_path = self._snapshot_volume_path.replace(snap_name, self.get_parent_name())
        (size, unit) = self.get_size()
        if self.remove():
            if self.recreate(snap_name, parent_path, size, unit):
                return True
        return False
