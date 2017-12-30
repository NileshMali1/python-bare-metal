import subprocess


class LVMExec(object):
    """ to execute lvm commands """

    @classmethod
    def exec(cls, argument_list=None):
        if not argument_list:
            return None
        try:
            output = subprocess.check_output(argument_list)
            if output:
                return output.decode("utf-8")
        except Exception as e:
            print(str(e))
        return None