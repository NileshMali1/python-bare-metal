from lvm2.helper import Helper
import os
import re


class PhysicalVolume(object):
    """Wrapper for physical volume"""

    def __init__(self, pv_path):
        self._pv_path = pv_path

    @classmethod
    def create(cls, disk_partition_path):
        output = Helper.exec(["pvcreate", disk_partition_path])
        if output and 'Physical volume "'+disk_partition_path+'" successfully created.' in output:
            return True
        return False

    @classmethod
    def get_all(cls):
        output = Helper.exec(["pvdisplay", "-c"])
        pvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line or "is a new physical volume of" in line:
                    continue
                pvs.append(PhysicalVolume(line.split(":")[0]))
        return pvs

    def get_info(self):
        output = Helper.exec(["pvdisplay", self._pv_path])
        if output:
            is_new = False
            info = Helper.format(output, "--- Physical volume ---")
            if not info:
                info = Helper.format(output, "--- NEW Physical volume ---")
                if info:
                    is_new = True
            info["NEW"] = is_new
            return info
        return None

    def _filter_info(self, filter_key=None):
        info = self.get_info()
        if info and filter_key:
            if filter_key in info:
                return info[filter_key]
            else:
                return None
        return info

    def get_name(self):
        return self._filter_info("PV Name")

    def is_new(self):
        return self._filter_info("NEW")

    def get_volume_group(self):
        return self._filter_info("VG Name")

    def remove(self):
        output = Helper.exec(["pvremove", self._pv_path])
        if output and 'Labels on physical volume "'+self._pv_path+'" successfully wiped.' in output:
            return True
        return False


class VolumeGroup(object):
    """ VG Ops """

    def __init__(self, vg_name):
        self._vg_name = vg_name

    def get_name(self):
        return self._vg_name

    @classmethod
    def create(cls, vg_name, pv_list):
        command = ["vgcreate", vg_name]
        if pv_list is list:
            command.extend(pv_list)
        else:
            command.append(pv_list)
        output = Helper.exec(command)
        if output and 'Volume group "' + vg_name + '" successfully created' in output:
            return True
        return False

    @classmethod
    def get_all(cls):
        output = Helper.exec(["vgdisplay", "-c"])
        vgs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                vgs.append(VolumeGroup(line.split(":")[0]))
        return vgs

    def remove(self):
        output = Helper.exec(["vgremove", self._vg_name])
        if output and 'Volume group "' + self._vg_name + '" successfully removed' in output:
            self._vg_name = None
            return True
        return False

    def include_physical_volume(self, pv):
        output = Helper.exec(["vgextend", self._vg_name, pv.get_name()])
        if output:
            return True
        return False

    def exclude_physical_volume(self, pv):
        output = Helper.exec(["vgreduce", self._vg_name, pv.get_name()])
        if output:
            return True
        return False

    def create_logical_volume(self, lv_name, size=10.0, unit="GiB"):
        output = Helper.exec(["lvcreate", "--name", lv_name, "--size", str(size)+unit, self._vg_name])
        if output and 'Logical volume "' + lv_name + '" created' in output:
            return True
        return False

    def _is_snapshot(self, lv_path):
        output = Helper.exec(["lvs", lv_path])
        if output:
            for line in output.split("\n"):
                if self._vg_name not in line:
                    continue
                line = line.strip()
                columns = line.split(" ")
                return True if columns[2].lower().startswith("s") else False
        return None

    def get_logical_volumes(self):
        output = Helper.exec(["lvdisplay", "-c"])
        lvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                columns = line.split(":")
                if columns[1] == self._vg_name and not self._is_snapshot(columns[0]):
                    lvs.append(LogicalVolume(columns[0]))
        return lvs

    def get_physical_volumes(self):
        output = Helper.exec(["pvdisplay", "-c"])
        pvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                columns = line.split(":")
                if columns[1] == self._vg_name:
                    pvs.append(PhysicalVolume(columns[0]))
        return pvs


class LogicalVolume(object):
    """ LV Ops """

    def __init__(self, volume_path):
        self._volume_path = volume_path

    def get_info(self):
        output = Helper.exec(["lvdisplay", self._volume_path])
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
        snapshots = self._filter_info("source_of")
        if snapshots:
            return [Snapshot(self._volume_path.replace(self.get_name(), snapshot)) for snapshot in snapshots]
        return None

    def get_name(self):
        return self._filter_info("LV Name")

    def get_path(self):
        return self._filter_info("LV Path")

    def get_size(self):
        return self._filter_info("LV Size").split(" ")

    def get_volume_group(self):
        return VolumeGroup(self._filter_info("VG Name"))

    def rename(self, new_name):
        old_name = self.get_name()
        vg = self.get_volume_group()
        output = Helper.exec(["lvrename", vg.get_name(), old_name, new_name])
        if output and "Renamed \""+old_name+"\" to \""+new_name+"\" in volume group \""+vg.get_name()+"\"":
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


class Snapshot(LogicalVolume):
    """A snapshot object for logical volume"""

    def __init__(self, snapshot_volume_path):
        super().__init__(snapshot_volume_path)

    def get_parent(self):
        result = self._filter_info("LV snapshot status")
        if result:
            matcher = re.search(r"active destination for ([a-zA-Z0-9]+)", result)
            if matcher:
                return LogicalVolume(self._volume_path.replace(self.get_name(), matcher.group(1)))
        return None

    def recreate(self, snapshot_name, lv_path, size=5.0, unit="GiB"):
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
