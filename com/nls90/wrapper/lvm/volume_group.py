from com.nls90.wrapper.lvm.lvm_exec import LVMExec


class VolumeGroup(object):
    """ VG Ops """

    def __init__(self, vg_name):
        self._vg_name = vg_name

    @classmethod
    def create(cls, vg_name, pv_list):
        if pv_list is not list:
            pv_list = list(pv_list)
        command = ["vgcreate", vg_name]
        command.extend(pv_list)
        output = LVMExec.exec(command)
        if output and 'Volume group "' + vg_name + '" successfully created' in output:
            return True
        return False

    @classmethod
    def remove(cls, vg_name):
        output = LVMExec.exec(["vgremove", vg_name])
        if output and 'Volume group "' + vg_name + '" successfully removed' in output:
            return True
        return False

    @classmethod
    def list(cls, vg_name=None):
        args = ["vgdisplay"]
        if vg_name:
            args.append(vg_name)
        output = LVMExec.exec(args)
        if output:
            return output
        return None