from lvm2.helper import Helper
from lvm2.logical_volume import LogicalVolume
from lvm2.physical_volume import PhysicalVolume


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
                if not line: continue
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
                if not line: continue
                columns = line.split(":")
                if columns[1] == self._vg_name:
                    pvs.append(PhysicalVolume(columns[0]))
        return pvs

