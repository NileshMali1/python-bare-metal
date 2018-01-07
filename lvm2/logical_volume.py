import os
from lvm2.helper import Helper
from lvm2.logical_volume_snapshot import LogicalVolumeSnapshot


class LogicalVolume(object):
    """ LV Ops """

    def __init__(self, volume_path):
        self._volume_path = volume_path

    def get_info(self):
        args = ["lvdisplay", self._volume_path]
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

    def get_snapshots(self):
        snapshot_names = self._filter_info("source_of")
        if snapshot_names:
            return [LogicalVolumeSnapshot(self._volume_path.replace(self.get_name(), snapshot_name))
                     for snapshot_name in snapshot_names]
        return None

    def get_name(self):
        return self._filter_info("LV Name")

    def get_path(self):
        return self._filter_info("LV Path")

    def get_size(self):
        return self._filter_info("LV Size").split(" ")

    def get_volume_group(self):
        return self._filter_info("VG Name")

    def rename(self, new_name):
        old_name = self.get_name()
        vg_name = self.get_volume_group()
        output = Helper.exec(["lvrename", vg_name, old_name, new_name])
        if output and "Renamed \""+old_name+"\" to \""+new_name+"\" in volume group \""+vg_name+"\"":
            self._volume_path = self._volume_path.replace(old_name, new_name)
            return True
        return False

    def create_snapshot(self, snapshot_name, size=5.0, unit="GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", self._volume_path, "--size", str(size)+unit]
        output = Helper.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            return True
        return False

    def remove(self):
        output = Helper.exec(["lvremove", "--force", self._volume_path])
        if output and 'Logical volume "' + os.path.basename(self._volume_path) + '" successfully removed' in output:
            self._volume_path = None
            return True
        return False
