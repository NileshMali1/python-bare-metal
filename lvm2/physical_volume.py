from lvm2.helper import Helper


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
        return  self._filter_info("NEW")

    def get_volume_group(self):
        return self._filter_info("VG Name")

    def remove(self):
        output = Helper.exec(["pvremove", self._pv_path])
        if output and 'Labels on physical volume "'+self._pv_path+'" successfully wiped.' in output:
            return True
        return False

