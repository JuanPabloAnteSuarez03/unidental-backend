from rest_framework import serializers
from django.contrib.auth.models import User, Group
from django.contrib.auth.password_validation import validate_password

ALLOWED_ROLES = ['User', 'Admin']

class AdminUserCreateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=[(r, r) for r in ALLOWED_ROLES])
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(**validated_data)
        group = Group.objects.get(name=role)
        user.groups.add(group)
        # Ya NO se asignan is_staff ni is_superuser automáticamente
        return user


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        try:
            user_group = Group.objects.get(name='User')
            user.groups.add(user_group)
        except Group.DoesNotExist:
            pass
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Serializador para mostrar información del usuario incluyendo su rol.
    """
    role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']
        read_only_fields = ['id', 'role']

    def get_role(self, obj):
        """Obtener el rol principal del usuario."""
        if obj.groups.filter(name='Admin').exists():
            return 'Admin'
        elif obj.groups.filter(name='User').exists():
            return 'User'
        else:
            return 'Sin rol' 