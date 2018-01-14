import subprocess
import re


class Helper(object):
    """ to execute lvm2 commands """

    @staticmethod
    def exec_mount(device, offset, mount_point, mode="rw"):
        args = ["mount"]
        options = ["loop", "offset="+offset]
        if mode == "ro":
            options.insert(1, mode)
        else:
            args.append("--rw")
        args.extend(["--options", ','.join(options), device, mount_point])
        output = subprocess.check_output(args)
        if output:
            return output.decode("utf-8")
        return None
    
    @staticmethod
    def exec_umount(mount_point):
        output = subprocess.check_output(["umount", "-f", mount_point])
        if output:
            return output.decode("utf-8")
        return None

    @staticmethod
    def exec_fdisk(device=None):
        if device:
            output = subprocess.check_output(["fdisk", "-u=sectors", "--bytes", "-l", device])
        else:
            output = subprocess.check_output(["fdisk", "-l"])
        if output:
            return output.decode("utf-8")
        return None

    @staticmethod
    def exec_dd(source, destination):
        if not (source and destination):
            return None
        output = subprocess.check_output(["dd", "if="+source, "of="+destination, "bs=4M"])
        if output:
            return output.decode("utf-8")
        return None

    @staticmethod
    def format(output, section_start):
        section = False
        source_of = False
        info = {}
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                section = False
                break
            if section_start in line:
                section = True
                continue
            if section:
                try:
                    splits = re.split(r"\s\s+", line)
                    if not source_of and "source of" in splits[1]:
                        source_of = True
                        continue
                    if len(splits) == 1 and source_of:
                        match = re.search(r"([a-zA-z0-9]+)\s+", splits[0])
                        if match:
                            if not "source_of" in info:
                                info["source_of"] = []
                            info["source_of"].append(match.group(1))
                    else:
                        info[splits[0]] = splits[1]
                        if source_of:
                            source_of = False
                except IndexError as ie:
                    if "host, time" in line:
                        splits = re.split(r"time\s+", line)
                        info[splits[0]+'time'] = splits[1]
                except Exception as e:
                    print(str(e))
        return info

    @staticmethod
    def exec(argument_list=None):
        if not argument_list:
            return None
        try:
            output = subprocess.check_output(argument_list)
            if output:
                return output.decode("utf-8")
        except Exception as e:
            print(str(e))
        return None