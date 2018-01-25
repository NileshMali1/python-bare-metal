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

    def exists(self):
        output = self._execute(["--op", "show"])
        if output:
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "Target " + self.get_id() + ": " + self.get_name() in line:
                    return True
        return False

    def get_logical_unit_number(self, device_path):
        output = self._execute(["--op", "show"])
        lun = None
        device_found = False
        if output:
            target_found = False
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "Target " in line:
                    target_found = True if\
                        not target_found and "Target "+self.get_id()+": "+self.get_name() in line\
                        else False
                    continue
                if not target_found:
                    continue
                match = re.search(r"^LUN: (\d+)$", line)
                if match:
                    lun = match.group(1)
                    continue
                if lun and target_found:
                    if "Backing store path: "+device_path in line:
                        device_found = True
                        break
        return (lun, device_found) if device_found else (str(int(lun)+1), device_found)

    def get_details(self):
        output = self._execute(["--op", "show", "--tid", self._id])
        if output:
            return output
        return None

    def add(self):
        output = self._execute(["--op", "new", "--tid", self._id, "--targetname", self._name])
        if output:
            return False
        return True

    def remove(self):
        output = self._execute(["--op", "delete", "--tid", self._id, "--force"])
        if output:
            return False
        return True

    def attach_logical_unit(self, block_device_path, lun):
        output = self._execute(
            ["--op", "new", "--tid", self._id, "--lun", lun,
             "--backing-store", block_device_path], "logicalunit"
        )
        if output:
            return False
        return True

    def detach_logical_unit(self, lun):
        output = self._execute(["--op", "delete", "--tid", self._id, "--lun", lun], "logicalunit")
        if output:
            return False
        return True

    def _bind_or_unbind(self, operation, initiator=None, by="address"):
        if by not in ("address", "name"):
            by = "name"
        if initiator:
            by_value = initiator.get_address() if by == "address" else initiator.get_name()
        else:
            by_value = "ALL"
            by = "address"
        output = self._execute(["--op", operation, "--tid", self._id, "--initiator-"+by, by_value])
        if output:
            return False
        return True

    def bind_to_initiator(self, initiator=None, by="address"):
        return self._bind_or_unbind("bind", initiator, by)

    def unbind_from_initiator(self, initiator=None, by="address"):
        return self._bind_or_unbind("unbind", initiator, by)
