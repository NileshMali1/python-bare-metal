import subprocess
import re


class ISCSITarget(object):
    """a wrapper for tgtadm tool"""

    @staticmethod
    def get_iscsi_qualified_name(name):
        return "%s:%s" % (r"iqn.2018-01.com.nls90.iscsitarget", name)

    def __init__(self, tid, tname):
        self._id = str(tid)
        self._name = self.get_iscsi_qualified_name(tname)
        self._logical_unit_number = None

    def get_id(self):
        return self._id

    def get_name(self):
        return self._name

    def set_id(self, tid):
        self._id = tid

    def set_name(self, name):
        self._name = self.get_iscsi_qualified_name(name)

    @staticmethod
    def _execute(args, mode="target"):
        arguments = ["tgtadm", "--lld", "iscsi", "--mode", mode]
        arguments.extend(args)
        try:
            output = subprocess.check_output(arguments)
            if output:
                output = output.decode("utf-8")
            if output:
                return output
        except Exception as e:
            print(str(e))
        return None

    def get_current_logical_unit_number(self):
        output = self._execute(["--op", "show"])
        lun = None
        if output:
            target_found = False
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "Target "+self.get_id()+": "+self.get_name() in line:
                    target_found = True
                    continue
                if target_found:
                    if "Target " in line:
                        target_found = False
                        continue
                    match = re.search(r"^LUN: (\d+)$", line)
                    if match:
                        lun = int(match.group(1))
        return lun

    def get_details(self):
        output = self._execute(["--op", "show", "--tid", self._id])
        if output:
            return output
        return None

    def add(self):
        output = self._execute(["--op", "new", "--tid", self._id, "--targetname", self._name])
        if output:
            print(output)
            return False
        return True

    def remove(self):
        output = self._execute(["--op", "delete", "--tid", self._id, "--force"])
        if output:
            print(output)
            return False
        return True

    def attach_logical_unit(self, block_device_path):
        self._logical_unit_number = str(self.get_current_logical_unit_number() + 1)
        output = self._execute(
            ["--op", "new", "--tid", self._id, "--lun", self._logical_unit_number,
             "--backing-store", block_device_path], "logicalunit"
        )
        if output:
            print(output)
            return False
        return True

    def detach_logical_unit(self):
        output = self._execute(["--op", "delete", "--tid", self._id, "--lun", self._logical_unit_number], "logicalunit")
        if output:
            print(output)
            return False
        return True

    def _bind_or_unbind(self, operation, initiator, by="address"):
        if by not in ("address", "name"):
            by = "name"
        by_value = initiator.get_address() if by == "address" else initiator.get_name()
        output = self._execute(["--op", operation, "--tid", self._id, "--initiator-"+by, by_value])
        if output:
            print(output)
            return False
        return True

    def bind_to_initiator(self, initiator, by="address"):
        return self._bind_or_unbind("bind", initiator, by)

    def unbind_from_initiator(self, initiator, by="address"):
        return self._bind_or_unbind("unbind", initiator, by)
