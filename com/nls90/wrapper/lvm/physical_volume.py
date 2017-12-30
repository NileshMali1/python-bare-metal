from com.nls90.wrapper.lvm.lvm_exec import LVMExec


class PhysicalVolume(object):
    """Wrapper for physical volume"""

    def __init__(self, pv_path):
        self._pv_path = pv_path

    @classmethod
    def create(cls, disk_partition_path):
        if not disk_partition_path:
            return False
        output = LVMExec.exec(["pvcreate", disk_partition_path])
        if output and 'Physical volume "'+disk_partition_path+'" successfully created.' in output:
            return True
        return False

    @classmethod
    def remove(cls, pv_path):
        if not pv_path:
            return False
        output = LVMExec.exec(["pvremove", pv_path])
        if output and 'Labels on physical volume "'+pv_path+'" successfully wiped.' in output:
            return True
        return False

    @classmethod
    def list(cls, pv_path=None):
        args = ["pvdisplay"]
        if pv_path:
            args.append(pv_path)
        output = LVMExec.exec(args)
        if output:
            return output
        return None