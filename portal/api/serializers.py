from rest_framework import serializers
from api.models import ControlDevice, Initiator, Target, LogicalUnit, Snapshot


class ControlDeviceSerializer(serializers.HyperlinkedModelSerializer):
    pdu_endpoint = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="initiator-detail")
    kvm_endpoint = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="initiator-detail")

    class Meta:
        model = ControlDevice
        fields = '__all__'


class InitiatorSerializer(serializers.HyperlinkedModelSerializer):
    target = serializers.HyperlinkedRelatedField(many=False, read_only=True, view_name="target-detail")

    class Meta:
        model = Initiator
        fields = '__all__'


class TargetSerializer(serializers.HyperlinkedModelSerializer):
    logical_units = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="logicalunit-detail")

    class Meta:
        model = Target
        fields = '__all__'


class LogicalUnitSerializer(serializers.HyperlinkedModelSerializer):
    snapshots = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="snapshot-detail")

    class Meta:
        model = LogicalUnit
        fields = '__all__'


class SnapshotSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Snapshot
        fields = '__all__'
