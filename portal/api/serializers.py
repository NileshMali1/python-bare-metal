from rest_framework import serializers
from api.models import Initiator, Target, Snapshot


class InitiatorSerializer(serializers.HyperlinkedModelSerializer):
    targets = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="target-detail")

    class Meta:
        model = Initiator
        fields = '__all__'


class TargetSerializer(serializers.HyperlinkedModelSerializer):
    snapshots = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name="snapshot-detail")

    class Meta:
        model = Target
        fields = '__all__'


class SnapshotSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Snapshot
        fields = '__all__'
