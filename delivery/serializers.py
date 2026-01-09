from rest_framework import serializers
from .models import (
    DeliveryRequest, DeliveryPerson, DeliveryService, DeliveryZone,
    DeliveryStatusHistory, DeliveryRating, DeliveryProof, DeliveryRoute,
    DeliveryNotification, DeliveryPackageType, DeliveryTimeSlot,
    DeliveryPricingRule
)


class DeliveryServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryService
        fields = '__all__'


class DeliveryPersonSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    
    class Meta:
        model = DeliveryPerson
        fields = '__all__'
        read_only_fields = ['rating', 'total_deliveries', 'completed_deliveries']


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = '__all__'


class DeliveryStatusHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField()
    
    class Meta:
        model = DeliveryStatusHistory
        fields = '__all__'
        read_only_fields = ['created_at']


class DeliveryProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryProof
        fields = '__all__'
        read_only_fields = ['created_at']


class DeliveryRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRating
        fields = '__all__'
        read_only_fields = ['created_at']


class DeliveryRequestSerializer(serializers.ModelSerializer):
    delivery_service = DeliveryServiceSerializer(read_only=True)
    delivery_zone = DeliveryZoneSerializer(read_only=True)
    delivery_person = DeliveryPersonSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = DeliveryRequest
        fields = '__all__'
        read_only_fields = [
            'tracking_number', 'created_at', 'updated_at',
            'metadata', 'pickup_time', 'actual_delivery_time'
        ]
    
    def to_representation(self, instance):
        """Customize the output"""
        representation = super().to_representation(instance)
        
        # Add calculated distance if coordinates exist
        if instance.pickup_latitude and instance.recipient_latitude:
            try:
                distance = instance.calculate_distance()
                if distance:
                    representation['calculated_distance_km'] = distance
            except:
                pass
        
        # Format metadata for better readability
        if representation.get('metadata'):
            representation['metadata'] = instance.metadata
        
        return representation


class DeliveryRouteSerializer(serializers.ModelSerializer):
    delivery_person = DeliveryPersonSerializer(read_only=True)
    deliveries = DeliveryRequestSerializer(many=True, read_only=True)
    
    class Meta:
        model = DeliveryRoute
        fields = '__all__'
        read_only_fields = ['created_at', 'route_data']


class DeliveryNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryNotification
        fields = '__all__'
        read_only_fields = ['created_at']


class DeliveryPackageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPackageType
        fields = '__all__'


class DeliveryTimeSlotSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = DeliveryTimeSlot
        fields = '__all__'


class DeliveryPricingRuleSerializer(serializers.ModelSerializer):
    applies_to = DeliveryServiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = DeliveryPricingRule
        fields = '__all__'
        read_only_fields = ['created_at']