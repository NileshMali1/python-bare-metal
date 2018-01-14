import os
import re

from helpers.lvm2.helper import Helper


class Disk(object):
    """An general disk device object. Physical Disk, LVM LV, VMDK and other block devices are or could be disk"""

    def __init__(self, device_path):
        self._device_path = device_path
        self._sector_size = None

    @staticmethod
    def get_all():
        fd_output = Helper.exec_fdisk()
        disks = []
        if fd_output:
            for line in fd_output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                match = re.search(r"^Disk\s+(\\dev\\sd[a-z]):", line)
                if match:
                    disks.append(match.group(1))
        return disks

    def get_path(self):
        return self._device_path

    def set_sector_size(self, sector_size):
        self._sector_size = sector_size

    def get_sector_size(self):
        return self._sector_size

    def get_partitions(self):
        metadata = Helper.exec_fdisk(self.get_path())
        partitions = []
        if metadata:
            partition_section_columns = 0
            for line in metadata.split("\n"):
                line = line.strip()
                if not line:
                    continue
                match = re.search("Sector size .*?: (\d+) bytes", line)
                if match:
                    self.set_sector_size(int(match.group(1)))
                    continue
                if re.search(r"Device\s+Boot\s+Start\s+End", line):
                    partition_section_columns = len(line.split())
                    continue
                if partition_section_columns > 0:
                    splits = line.split()
                    if re.search(r"\d+", splits[1]):
                        splits.insert(1, False)
                    else:
                        splits[1] = True
                    if len(splits) > 7:
                        extra_splits = splits[8:]
                        splits[7] += ' ' + ' '.join(extra_splits)
                        for extra_split in extra_splits:
                            splits.remove(extra_split)
                    partitions.append(Partition(splits[0], splits[1:]))
        return partitions

    def mount(self, mount_location):
        for partition in self.get_partitions():
            if partition.compute_size(self.get_sector_size(), "gb") > 2:
                offset = partition.get_sector_start() * self.get_sector_size()
                output = Helper.exec_mount(self.get_path(), offset, mount_location)
                if output:
                    return True
        return False

    def unmount(self, mount_location):
        output = Helper.exec_umount(mount_location)
        if output:
            return True
        return False


class Partition(object):
    """A disk partition object populated by fdisk command"""

    def __init__(self, path_id, args=None):
        self._path_id = path_id
        self._boot_flag = False
        self._start = None
        self._end = None
        self._sectors = None
        self._size = None
        self._id = None
        self._type = None
        if args and len(args) == 7:
            self._set_all(args)

    def _set_all(self, args):
        self._boot_flag = args[0]
        self._start = int(args[1])
        self._end = int(args[2])
        self._sectors = int(args[3])
        self._size = int(args[4])
        self._id = int(args[5])
        self._type = args[6]

    def get_path_id(self):
        return self._path_id

    def get_disk(self):
        pass

    def is_bootable(self):
        return self._boot_flag

    def get_sector_start(self):
        return self._start

    def get_sector_end(self):
        return self._end

    def get_sectors(self):
        return self._sectors

    def get_size(self):
        return self._size

    def get_id(self):
        return self._id

    def get_type(self):
        return self._type

    def compute_size(self, unit="gb"):
        divide_by = 1
        if unit.lower() == "gb":
            divide_by = 1024*1024*1024
        elif unit.lower() == "mb":
            divide_by = 1024*1024
        size_in_bytes = self.get_size()
        return int(size_in_bytes/divide_by) if size_in_bytes else None


class PhysicalVolume(Partition):
    """LVMs Physical Volume object"""

    def __init__(self, pv_path):
        super().__init__(pv_path)

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
        output = Helper.exec(["pvdisplay", self._path_id])
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
        return VolumeGroup(self._filter_info("VG Name"))

    def remove(self):
        output = Helper.exec(["pvremove", self.get_path_id()])
        if output and 'Labels on physical volume "'+self.get_path_id()+'" successfully wiped.' in output:
            return True
        return False


class VolumeGroup(object):
    """ LVMs Volume group object, it acts as a container grouping disk types """

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

    def create_logical_volume(self, lv_name, size, unit="GiB"):
        if lv_name and size:
            output = Helper.exec(["lvcreate", "--name", lv_name, "--size", str(size)+unit, self._vg_name])
            if output and 'Logical volume "' + lv_name + '" created' in output:
                return True
        return False

    def remove_logical_volume(self, lv_name):
        if lv_name:
            output = Helper.exec(["lvremove", "--force", self._vg_name+'/'+lv_name])
            if output and 'Logical volume "' + lv_name + '" successfully removed' in output:
                return True
        return False

    def rename_logical_volume(self, lv_name, new_lv_name):
        if lv_name and new_lv_name:
            output = Helper.exec(["lvrename", self._vg_name, lv_name, new_lv_name])
            if output and "Renamed \""+lv_name+"\" to \""+new_lv_name+"\" in volume group \""+self._vg_name+"\"":
                return True
        return False

    def get_logical_volumes(self, name=None):

        def is_snapshot(lv_path):
            sub_output = Helper.exec(["lvs", lv_path])
            if sub_output:
                for sub_line in sub_output.split("\n"):
                    sub_line = sub_line.strip()
                    if not sub_line or self._vg_name not in sub_line:
                        continue
                    sub_columns = sub_line.split(" ")
                    return True if sub_columns[2].lower().startswith("s") else False
            return None

        output = Helper.exec(["lvdisplay", "-c"])
        lvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                columns = line.split(":")
                if name and name not in columns[0]:
                    continue
                if columns[1] == self._vg_name and not is_snapshot(columns[0]):
                    lvs.append(LogicalVolume(columns[0]))
        return lvs[0] if len(lvs) == 1 else lvs

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

    def get_physical_volumes(self, name=None):
        output = Helper.exec(["pvdisplay", "-c"])
        pvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                columns = line.split(":")
                if name and name not in columns[0]:
                    continue
                if columns[1] == self._vg_name:
                    pvs.append(PhysicalVolume(columns[0]))
        return pvs[0] if len(pvs) == 1 else pvs


class LogicalVolume(Disk):
    """ LV Ops """

    def __init__(self, volume_path):
        super().__init__(volume_path)

    def get_info(self):
        output = Helper.exec(["lvdisplay", self._device_path])
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

    def get_name(self):
        return self._filter_info("LV Name")

    def get_path(self):
        return self._filter_info("LV Path")

    def get_size(self):
        return self._filter_info("LV Size").split(" ")

    def get_volume_group(self):
        return VolumeGroup(self._filter_info("VG Name"))

    def dump_to_image(self, destination_path):
        return Helper.exec_dd(self.get_path(), destination_path)

    def restore_from_image(self, source_path):
        return Helper.exec_dd(source_path, self.get_path())

    def get_snapshots(self):
        snapshots = self._filter_info("source_of")
        if snapshots:
            return [Snapshot(self._device_path.replace(self.get_name(), snapshot)) for snapshot in snapshots]
        return None

    def create_snapshot(self, snapshot_name, size=5.0, unit="GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", self._device_path, "--size", str(size)+unit]
        output = Helper.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            return True
        return False


class Snapshot(LogicalVolume):
    """A snapshot object for logical volume"""

    def __init__(self, snapshot_volume_path):
        super().__init__(snapshot_volume_path)

    def get_size(self):
        return self._filter_info("COW-table size").split(" ")

    def get_parent(self):
        result = self._filter_info("LV snapshot status")
        if result:
            matcher = re.search(r"active destination for ([a-zA-Z0-9]+)", result)
            if matcher:
                return LogicalVolume(self._device_path.replace(self.get_name(), matcher.group(1)))
        return None

    def recreate(self, snapshot_name, lv_path, size=5.0, unit="GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", lv_path, "--size", str(size)+unit]
        output = Helper.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            self._device_path = lv_path.replace(os.path.basename(lv_path), snapshot_name)
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
