from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from amuse.api.v4.serializers.helpers import filter_invite_sensitive_data
from amuse.serializers import StringMapField
from amuse.tokens import user_invitation_token_generator
from users.models import TeamInvitation, UserArtistRole
from amuse.tasks import send_team_invite
from amuse.api.base.validators import validate_phone_number, validate_not_owner_email


class TeamInvitationSerializer(serializers.ModelSerializer):
    team_role = StringMapField(mapping=TeamInvitation.TEAM_ROLE_CHOICES)
    status = StringMapField(mapping=TeamInvitation.STATUS_CHOICES, read_only=True)

    class Meta:
        model = TeamInvitation
        fields = (
            'artist',
            'email',
            'phone_number',
            'team_role',
            'invitee',
            'first_name',
            'last_name',
            # read-only fields
            'id',
            'inviter',
            'status',
            'last_sent',
        )
        read_only_fields = ('id', 'inviter', 'status', 'last_sent')

    def validate_phone_number(self, value):
        return validate_phone_number(value)

    def validate(self, attrs):
        no_phone_value = (
            attrs.get('phone_number', "") == ""
            or attrs.get('phone_number', None) is None
        )
        no_email_value = (
            attrs.get('email', "") == "" or attrs.get('email', None) is None
        )

        validate_not_owner_email(self.context['request'].user, attrs.get('email'))

        if self.instance is not None:  # we're resending the invite
            email_changed = not no_email_value and self.instance.email != attrs.get(
                'email'
            )
            phone_changed = (
                not no_phone_value
                and self.instance.phone_number != attrs.get('phone_number')
            )

            minutes_since_last_sent = (
                timezone.now() - self.instance.last_sent
            ).total_seconds() / 60

            allow_by_recipient_changed_rule = phone_changed or email_changed
            allow_by_time_rule = (
                minutes_since_last_sent >= TeamInvitation.MIN_RESEND_MINUTES
            )

            resend_allowed = allow_by_time_rule or allow_by_recipient_changed_rule

            if not resend_allowed:
                raise serializers.ValidationError(
                    f'You can only resend the invitation every {TeamInvitation.MIN_RESEND_MINUTES} minutes.'
                )

            if self.instance.status == TeamInvitation.STATUS_ACCEPTED:
                raise serializers.ValidationError('Invitation already accepted.')
        else:
            if no_phone_value and no_email_value:
                raise serializers.ValidationError('Email or phone number required.')

        return attrs

    def validate_team_role(self, team_role):
        if team_role == TeamInvitation.TEAM_ROLE_OWNER:
            raise ValidationError('Team Invitation cannot be sent for role OWNER')
        return team_role

    def create(self, validated_data):
        inviter = self.context['request'].user
        artist = validated_data.get('artist')

        # check if user has permissions to create an invite
        can_create = UserArtistRole.objects.filter(
            user=inviter,
            artist=artist,
            type__in=[UserArtistRole.ADMIN, UserArtistRole.OWNER],
        )

        if not can_create.exists():
            raise PermissionDenied(
                'You have to be an Admin or Owner to create an invitation'
            )

        email = validated_data.get('email')
        phone_number = validated_data.get('phone_number')

        # check if there's already an invite sent to this email / phone
        if TeamInvitation.objects.filter(
            Q(artist=artist),
            Q(status=TeamInvitation.STATUS_PENDING),
            Q(email=email, email__isnull=False)
            | Q(phone_number=phone_number, phone_number__isnull=False),
        ).exists():
            raise ValidationError(
                'Invitation for this artist has already been sent to the specified phone number / email.'
            )

        team_role = validated_data.get('team_role')
        first_name = validated_data.get('first_name', None)
        last_name = validated_data.get('last_name', None)
        invitee = validated_data.get('invitee')

        payload = {
            'inviter_first_name': inviter.first_name,
            'inviter_last_name': inviter.last_name,
            'user_id': inviter.id,
            'artist_id': artist.id,
            'artist_name': artist.name,
            'invitee_id': invitee.id if invitee else None,
        }
        token = user_invitation_token_generator.make_token(payload)

        invitation = TeamInvitation.objects.create(
            inviter=inviter,
            invitee=invitee,
            email=email,
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            artist=artist,
            token=token,
            status=TeamInvitation.STATUS_PENDING,
            team_role=team_role,
        )

        send_team_invite.delay(
            {
                'artist_name': artist.name,
                'inviter_first_name': inviter.first_name,
                'inviter_last_name': inviter.last_name,
                'invitee_first_name': invitee.first_name if invitee else first_name,
                'invitee_last_name': invitee.last_name if invitee else last_name,
                'user_artist_role': team_role,
                'email': invitation.email,
                'phone_number': invitation.phone_number,
                'token': token,
                'invitation_id': invitation.id,
            }
        )

        return invitation

    def update(self, instance, validated_data):
        new_email = validated_data.get('email')
        new_phone_number = validated_data.get('phone_number')
        invitee = validated_data.get('invitee')

        # check if there's already an invite sent to this email / phone
        if (
            TeamInvitation.objects.filter(
                Q(artist=instance.artist),
                Q(status=TeamInvitation.STATUS_PENDING),
                Q(email=new_email, email__isnull=False)
                | Q(phone_number=new_phone_number, phone_number__isnull=False),
            )
            .exclude(id=instance.id)
            .exists()
        ):
            raise ValidationError(
                'Invitation (pending) for this artist has already been sent to the specified phone number / email.'
            )

        first_name = (
            invitee.first_name if invitee else validated_data.get('first_name', None)
        )
        last_name = (
            invitee.last_name if invitee else validated_data.get('last_name', None)
        )
        payload = {
            'inviter_first_name': instance.inviter.first_name,
            'inviter_last_name': instance.inviter.last_name,
            'user_id': instance.inviter.id,
            'artist_id': instance.artist.id,
            'artist_name': instance.artist.name,
            'invitee_id': invitee.id if invitee else None,
        }
        instance.token = user_invitation_token_generator.make_token(payload)

        # update the email address if necessary
        instance.email = new_email
        instance.phone_number = new_phone_number
        instance.invitee = invitee
        instance.first_name = first_name
        instance.last_name = last_name

        instance.status = TeamInvitation.STATUS_PENDING
        instance.last_sent = timezone.now()
        instance.save()

        send_team_invite.delay(
            {
                'artist_name': instance.artist.name,
                'inviter_first_name': instance.inviter.first_name,
                'inviter_last_name': instance.inviter.last_name,
                'invitee_first_name': first_name,
                'invitee_last_name': last_name,
                'user_artist_role': instance.team_role,
                'email': new_email,
                'phone_number': new_phone_number,
                'token': instance.token,
                'invitation_id': instance.id,
            }
        )

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context['request'].user
        artist = instance.artist

        if not user.is_admin_of_artist_team(artist):
            data = filter_invite_sensitive_data(data)
        return data
