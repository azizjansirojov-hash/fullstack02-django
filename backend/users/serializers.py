"""Serializers for user registration and login."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()

# Common disposable / throwaway domains — keep short; expand as needed.
DISPOSABLE_EMAIL_DOMAINS = frozenset(
    {
        'mailinator.com',
        'guerrillamail.com',
        'guerrillamail.de',
        '10minutemail.com',
        'tempmail.com',
        'yopmail.com',
        'trashmail.com',
        'sharklasers.com',
    }
)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(required=True, allow_blank=False)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError('Username is required.')
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return username

    def validate_email(self, value):
        email = (value or '').strip().lower()
        if not email:
            raise serializers.ValidationError('Email is required.')
        domain = email.rsplit('@', 1)[-1]
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            raise serializers.ValidationError(
                'Please use a permanent email address (disposable domains are not allowed).'
            )
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate(self, attrs):
        password = attrs['password']
        password_confirm = attrs['password_confirm']

        if password != password_confirm:
            raise serializers.ValidationError(
                {'password_confirm': 'Passwords do not match.'}
            )

        # Temporary user instance so attribute-similarity checks work correctly.
        temp_user = User(
            username=attrs['username'],
            email=attrs['email'],
        )
        try:
            validate_password(password, user=temp_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(trim_whitespace=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    default_error_messages = {
        'invalid_credentials': 'Invalid username or password.',
        'inactive': 'This account is inactive.',
    }

    def validate(self, attrs):
        username = attrs['username'].strip()
        password = attrs['password']

        user = authenticate(
            request=self.context.get('request'),
            username=username,
            password=password,
        )

        if user is None:
            # Avoid leaking whether the username exists.
            raise serializers.ValidationError(
                {'detail': self.error_messages['invalid_credentials']}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {'detail': self.error_messages['inactive']}
            )

        attrs['user'] = user
        return attrs
