from com.nls90.wrapper.lvm.lvm_exec import LVMExec
import os


class LogicalVolume(object):
    """ LV Ops """

    def __init__(self, lv_name):
        self._lv_name = lv_name

    @classmethod
    def create(cls, lv_name, vg_name, size=10):
        command = ["lvcreate", "--name", lv_name, "--size", str(size)+"GB", vg_name]
        output = LVMExec.exec(command)
        if output and 'Logical volume "' + lv_name + '" created' in output:
            return True
        return False

    @classmethod
    def create_snapshot(cls, snapshot_name, lv_path, size=5):
        command = ["lvcreate", "--name", snapshot_name, "--snapshot", lv_path, "--size", str(size) + "GB"]
        output = LVMExec.exec(command)
        if output and 'Logical volume "' + snapshot_name + '" created' in output:
            return True
        return False

    @classmethod
    def remove(cls, lv_path):
        output = LVMExec.exec(["lvremove", "--force", lv_path])
        if output and 'Logical volume "' + os.path.basename(lv_path) + '" successfully removed' in output:
            return True
        return False

    @classmethod
    def remove_snapshot(cls, snapshot_path):
        return cls.remove(snapshot_path)

    @classmethod
    def list(cls, lv_name=None):
        args = ["lvdisplay"]
        if lv_name:
            args.append(lv_name)
        output = LVMExec.exec(args)
        if output:
            return output
        return None

    @classmethod
    def list_snapshots(cls, lv):
        pass
