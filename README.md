# python-bare-metal
Bare-Metal is a nerwork boot platform wherein selected machines (aka "Initiators" in iSCSI protocol terminology) (with or without local HDD) connect to remote storage using iSCSI protocol.
The enablement of the remote storage happens through what is known as "Target" in iSCSI protocol terminology.
These targets can be created & destroyed dynamically, usually with the help of utilities like "tgtadm", "iscsi-targets", etc.
Also, these targets can be backed by one or more block-devices (such as LVM LV, RAID, A file, etc.), these block-devices in backing mode are called "Logical Units".

This project utilizes Linux LVMs'Logical volumes as backing devices for targets and TgtAdm for the configurations of targets for network attachment and boot process.
Wrappers have been created over lvm2 utility and tgtadm utility to simplify interactions and to expose just the useful functionaliy of the utilities.

Moreover, to simplify configuration related tasks, this platform exposes RESTful API which makes the platform usable to human-beings as well as computers.

Requirements:

For client machines:
1. A PXE boot enabled (with-disk or diskless) machine
2. NIC with 1 gbps bandwidth support [Required]
3. 1 GB of RAM would do but more wil do better
4. Disk [Optional]

For server machines:
1. A good processor with more the cores the better
2. 8GB+ RAM
3. Parellel storage (perhaps, 2 or more HDDs)
4. A good NIC with 1gbps bandwidth support
