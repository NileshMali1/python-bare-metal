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
            output = subprocess.check_output(arguments, stderr=subprocess.STDOUT)
            if output:
                output = output.decode("utf-8")
            if output:
                return output
        except subprocess.CalledProcessError as e:
            pass
        return None

    def exists(self):
        output = self._execute(["--op", "show", "--tid", self._id])
        if not output or "can't find the target" in output:
            return False
        return True

    def list_active_logical_units(self):
        logical_units = {}
        output = self._execute(["--op", "show"])
        if output:
            target_found = False
            current_logical_unit_number = None
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "Target " in line:
                    target_found = True if "Target "+self.get_id()+": "+self.get_name() in line else False
                    continue
                if not target_found:
                    continue
                match = re.search(r"^LUN: (\d+)$", line)
                if match:
                    current_logical_unit_number = match.group(1) if int(match.group(1)) > 0 else None
                    continue
                if not current_logical_unit_number:
                    continue
                match = re.search(r"Backing store path: (.*)$", line)
                if match and "/dev/" in match.group(1):
                    logical_units[match.group(1)] = current_logical_unit_number
        return logical_units

    def get_logical_unit_number(self, device_path):
        active_logical_units_info = self.list_active_logical_units()
        if active_logical_units_info and device_path in active_logical_units_info:
            return active_logical_units_info[device_path]
        return None

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
            ["--op", "new", "--tid", self._id, "--lun", str(lun),
             "--backing-store", block_device_path], "logicalunit"
        )
        if output:
            return False
        return True

    def detach_logical_unit(self, lun):
        output = self._execute(["--op", "delete", "--tid", self._id, "--lun", str(lun)], "logicalunit")
        if output:
            return False
        return True

    def detach_all_logical_units(self):
        active_logical_units = self.list_active_logical_units()
        if active_logical_units:
            for active_logical_unit_path in active_logical_units:
                self.detach_logical_unit(active_logical_units[active_logical_unit_path])

    def list_connections(self, initiator=None):
        connections = {}
        output = self._execute(["--op", "show", "--tid", self._id], "conn")
        if output:
            session_id = None
            connection_id = None
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                matched = re.match("Session: (\d+)", line)
                if matched:
                    session_id = matched.group(1)
                    continue
                if not session_id:
                    continue
                matched = re.match("Connection: (\d+)", line)
                if matched:
                    connection_id = matched.group(1)
                    continue
                if not connection_id:
                    continue
                matched = re.match("IP Address: ([0-9.]+)", line)
                if not matched:
                    continue
                if initiator and matched.group(1) != initiator.get_ip_address():
                    continue
                if matched.group(1) not in connections:
                    connections[matched.group(1)] = {}
                if session_id not in connections[matched.group(1)]:
                    connections[matched.group(1)][session_id] = set()
                connections[matched.group(1)][session_id].add(connection_id)
        return connections

    def close_connection(self, session_id, connection_id):
        output = self._execute(["--op", "delete", "--tid", self._id, "--sid", session_id, "--cid", connection_id], "conn")
        if output:
            return False
        return True

    def _close_connections(self, connections):
        if not connections:
            return True
        closed = []
        for ip_address in connections:
            for session_id in connections[ip_address]:
                for connection_id in connections[ip_address][session_id]:
                    closed.append(self.close_connection(session_id, connection_id))
        return all(closed)

    def close_initiator_connections(self, initiator):
        return self._close_connections(self.list_connections(initiator))

    def close_all_connections(self):
        return self._close_connections(self.list_connections())

    def _bind_or_unbind(self, operation, initiator=None, by="address"):
        if by not in ("address", "name"):
            by = "name"
        if initiator:
            by_value = initiator.get_ip_address() if by == "address" else initiator.get_name()
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
