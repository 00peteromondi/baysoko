from rest_framework import serializers
from ..models import (
    DeliveryRequest, DeliveryPerson, DeliveryService, DeliveryZone,
    DeliveryStatusHistory, DeliveryProof, DeliveryRating,
    DeliveryPackageType, DeliveryTimeSlot, DeliveryPricingRule
)
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class DeliveryPersonSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DeliveryPerson
        fields = [
            'id', 'user', 'employee_id', 'phone', 'vehicle_type',
            'vehicle_registration', 'current_status', 'is_available',
            'current_latitude', 'current_longitude', 'max_weight_capacity',
            'service_radius', 'rating', 'total_deliveries',
            'completed_deliveries', 'is_verified'
        ]
        read_only_fields = ['rating', 'total_deliveries', 'completed_deliveries']


class DeliveryServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryService
        fields = [
            'id', 'name', 'service_type', 'description',
            'base_price', 'price_per_kg', 'price_per_km',
            'estimated_days_min', 'estimated_days_max',
            'is_active', 'service_areas'
        ]


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = [
            'id', 'name', 'description', 'delivery_fee',
            'min_order_amount', 'is_active'
        ]


class DeliveryStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryStatusHistory
        fields = ['id', 'old_status', 'new_status', 'notes', 'created_at']
        read_only_fields = fields


class DeliveryProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryProof
        fields = [
            'id', 'proof_type', 'file', 'signature_data',
            'verification_code', 'recipient_name',
            'recipient_id_type', 'recipient_id_number',
            'notes', 'created_at'
        ]


class DeliveryRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRating
        fields = [
            'id', 'rating', 'comment', 'on_time',
            'packaging_quality', 'communication',
            'would_recommend', 'issues', 'created_at'
        ]


class DeliveryRequestSerializer(serializers.ModelSerializer):
    delivery_person = DeliveryPersonSerializer(read_only=True)
    delivery_service = DeliveryServiceSerializer(read_only=True)
    delivery_zone = DeliveryZoneSerializer(read_only=True)
    status_history = DeliveryStatusHistorySerializer(many=True, read_only=True)
    proofs = DeliveryProofSerializer(many=True, read_only=True)
    calculated_distance = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliveryRequest
        fields = [
            'id', 'tracking_number', 'order_id', 'status',
            'pickup_name', 'pickup_address', 'pickup_phone',
            'recipient_name', 'recipient_address', 'recipient_phone',
            'package_description', 'package_weight', 'declared_value',
            'is_fragile', 'requires_signature',
            'delivery_person', 'delivery_service', 'delivery_zone',
            'delivery_fee', 'tax_amount', 'insurance_fee', 'total_amount',
            'payment_status', 'pickup_time', 'estimated_delivery_time',
            'actual_delivery_time', 'created_at', 'updated_at',
            'status_history', 'proofs', 'calculated_distance'
        ]
        read_only_fields = fields
    
    def get_calculated_distance(self, obj):
        return obj.calculate_distance()


class DeliveryRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRequest
        fields = [
            'order_id', 'pickup_name', 'pickup_address', 'pickup_phone',
            'recipient_name', 'recipient_address', 'recipient_phone',
            'package_description', 'package_weight', 'declared_value',
            'is_fragile', 'requires_signature',
            'delivery_service', 'delivery_zone'
        ]
    
    def create(self, validated_data):
        # Generate tracking number
        from django.utils import timezone
        import uuid
        
        validated_data['tracking_number'] = f"DLV{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Calculate delivery fee
        from ..utils import calculate_delivery_fee
        fee = calculate_delivery_fee(
            weight=validated_data.get('package_weight'),
            service_type=validated_data.get('delivery_service'),
            zone=validated_data.get('delivery_zone')
        )
        validated_data['delivery_fee'] = fee
        validated_data['total_amount'] = fee
        
        # Set metadata
        validated_data['metadata'] = {
            'created_by': self.context['request'].user.username,
            'source': 'api'
        }
        
        return super().create(validated_data)


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    current_status = serializers.CharField(source='get_status_display')
    estimated_delivery = serializers.SerializerMethodField()
    status_updates = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliveryRequest
        fields = [
            'tracking_number', 'current_status',
            'pickup_name', 'pickup_address',
            'recipient_name', 'recipient_address',
            'estimated_delivery', 'status_updates'
        ]
    
    def get_estimated_delivery(self, obj):
        if obj.estimated_delivery_time:
            return obj.estimated_delivery_time.strftime('%Y-%m-%d %H:%M')
        return None
    
    def get_status_updates(self, obj):
        updates = obj.status_history.all().order_by('-created_at')[:5]
        return DeliveryStatusHistorySerializer(updates, many=True).data


class DeliveryPackageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPackageType
        fields = [
            'id', 'name', 'description', 'base_price',
            'max_weight', 'max_length', 'max_width', 'max_height',
            'icon', 'is_active'
        ]


class DeliveryTimeSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display')
    
    class Meta:
        model = DeliveryTimeSlot
        fields = [
            'id', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'max_orders',
            'orders_booked', 'is_active', 'is_available'
        ]


class DeliveryPricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPricingRule
        fields = [
            'id', 'name', 'rule_type', 'condition',
            'base_price', 'price_modifier', 'is_active',
            'priority', 'applies_to'
        ]