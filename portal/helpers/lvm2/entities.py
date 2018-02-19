import re
from helpers.lvm2.helper import Helper
from enum import Enum, unique
import inspect


@unique
class DiskStatus(Enum):
    OFFLINE = 0
    ONLINE = 1
    BUSY = 2
    MODIFIED = 3
    MOUNTED = 4

    @classmethod
    def choices(cls):
        members = inspect.getmembers(cls, lambda member: not (inspect.isroutine(member)))
        properties = [member for member in members if member[0][:2] != '__' and member[0] not in ['name', 'value']]
        choices = tuple([(str(property[1].value), property[0]) for property in properties])
        return choices


class Disk(object):
    """An general disk device object. Physical Disk, LVM LV, VMDK and other block devices are or could be disk"""

    def __init__(self, device_path):
        self._device_path = device_path
        self._sector_size = None

    @staticmethod
    def get_all():
        fd_output = Helper.execute_fdisk()
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
        metadata = Helper.execute_fdisk(self.get_path())
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
            if partition.compute_size() <= 1:  # self.get_sector_size(), "gb"
                continue
            offset = partition.get_sector_start() * self.get_sector_size()
            output = Helper.execute_mount(self.get_path(), offset, mount_location)
            if not output:
                return True
        return False

    def unmount(self, mount_location):
        output = Helper.execute_umount(mount_location)
        if not output:
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
        output = Helper.execute(["pvcreate", disk_partition_path])
        if output and 'Physical volume "'+disk_partition_path+'" successfully created.' in output:
            return True
        return False

    @classmethod
    def get_all(cls):
        output = Helper.execute(["pvdisplay", "-c"])
        pvs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line or "is a new physical volume of" in line:
                    continue
                pvs.append(PhysicalVolume(line.split(":")[0]))
        return pvs

    def get_info(self):
        output = Helper.execute(["pvdisplay", self._path_id])
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
        output = Helper.execute(["pvremove", self.get_path_id()])
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
        output = Helper.execute(command)
        if output and 'Volume group "' + vg_name + '" successfully created' in output:
            return True
        return False

    @classmethod
    def get_all(cls):
        output = Helper.execute(["vgdisplay", "-c"])
        vgs = []
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                vgs.append(VolumeGroup(line.split(":")[0]))
        return vgs

    def remove(self):
        output = Helper.execute(["vgremove", self._vg_name])
        if output and 'Volume group "' + self._vg_name + '" successfully removed' in output:
            self._vg_name = None
            return True
        return False

    def contains_logical_volume(self, lv_name):
        output = Helper.execute(["lvdisplay", "-c"])
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                columns = line.split(":")
                if lv_name in columns[0] and columns[1] == self._vg_name:
                    return True
        return False

    def create_logical_volume(self, lv_name, size, unit="GiB"):
        if lv_name and size:
            output = Helper.execute(["lvcreate", "--name", lv_name,
                                  "--size", str(size)+unit, "-W", "y", self._vg_name])
            if output and 'Logical volume "' + lv_name + '" created' in output:
                return True
        return False

    def remove_logical_volume(self, lv_name):
        if lv_name:
            output = Helper.execute(["lvremove", "--force", self._vg_name+'/'+lv_name])
            if output and 'Logical volume "' + lv_name + '" successfully removed' in output:
                return True
        return False

    def rename_logical_volume(self, lv_name, new_lv_name):
        if lv_name and new_lv_name:
            output = Helper.execute(["lvrename", self._vg_name, lv_name, new_lv_name])
            if output and "Renamed \""+lv_name+"\" to \""+new_lv_name+"\" in volume group \""+self._vg_name+"\"":
                return True
        return False

    def get_logical_volumes(self, name=None):

        def is_snapshot(lv_path):
            sub_output = Helper.execute(["lvs", lv_path])
            if sub_output:
                for sub_line in sub_output.split("\n"):
                    sub_line = sub_line.strip()
                    if not sub_line or self._vg_name not in sub_line:
                        continue
                    sub_columns = sub_line.split(" ")
                    return True if sub_columns[2].lower().startswith("s") else False
            return None

        output = Helper.execute(["lvdisplay", "-c"])
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
        return lvs

    def include_physical_volume(self, pv):
        output = Helper.execute(["vgextend", self._vg_name, pv.get_name()])
        if output:
            return True
        return False

    def exclude_physical_volume(self, pv):
        output = Helper.execute(["vgreduce", self._vg_name, pv.get_name()])
        if output:
            return True
        return False

    def get_physical_volumes(self, name=None):
        output = Helper.execute(["pvdisplay", "-c"])
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
        output = Helper.execute(["lvdisplay", self._device_path])
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
        return Helper.execute_dd(self.get_path(), destination_path)

    def restore_from_image(self, source_path):
        return Helper.execute_dd(source_path, self.get_path())

    def contains_snapshot(self, snap_name):
        snapshots = self._filter_info("source_of")
        if snapshots and snap_name in snapshots:
            return True
        return False

    def get_snapshots(self, snap_name=None):
        snapshots = self._filter_info("source_of")
        if snapshots:
            if snap_name:
                return [Snapshot(self._device_path.replace(self.get_name(), snapshot))
                        for snapshot in snapshots if snapshot == snap_name]
            else:
                return [Snapshot(self._device_path.replace(self.get_name(), snapshot)) for snapshot in snapshots]
        return None

    def create_snapshot(self, snapshot_name, size, unit="GiB"):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", self._device_path, "--size", str(size)+unit]
        output = Helper.execute(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            return True
        return False

    def remove_snapshot(self, snap_name):
        if snap_name:
            output = Helper.execute(["lvremove", "--force", self.get_volume_group().get_name()+'/'+snap_name])
            if output and 'Logical volume "' + snap_name + '" successfully removed' in output:
                return True
        return False

    def revert_to_snapshot(self, snap_name):
        snaps = self.get_snapshots(snap_name)
        if not snaps:
            return False
        (size, unit) = snaps[0].get_size()
        if self.remove_snapshot(snap_name):
            if self.create_snapshot(snap_name, size, unit):
                return True
        return False

    def rename_snapshot(self, snap_name, new_snap_name):
        if snap_name and new_snap_name:
            output = Helper.execute(["lvrename", self.get_volume_group().get_name(), snap_name, new_snap_name])
            if output and "Renamed \"" + snap_name + "\" to \"" + new_snap_name + "\" in volume group \"" + \
                    self.get_volume_group().get_name()+"\"":
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

    def get_snapshots(self, snap_name=None):
        raise Exception("Not applicable since snapshot(s) of snapshot is not supported.")

    def create_snapshot(self, snapshot_name, size, unit="GiB"):
        raise Exception("Not applicable since snapshot(s) of snapshot is not supported.")

    def remove_snapshot(self, snap_name):
        raise Exception("Not applicable since snapshot(s) of snapshot is not supported.")

    def revert_to_snapshot(self, snap_name):
        raise Exception("Not applicable since snapshot(s) of snapshot is not supported.")

    def rename_snapshot(self, snap_name, new_snap_name):
        raise Exception("Not applicable since snapshot(s) of snapshot is not supported.")
