from pkgutil import read_code
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from rest_framework import serializers

from . import models

# Nested


class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "first_name", "last_name", "type")


class NestedOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Organization
        fields = ("id", "name", "type")


class NestedMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Membership
        fields = ("organization", "points", "points_spent")

    organization = NestedOrganizationSerializer(read_only=True)


class NestedPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Period
        fields = ("id", "name", "customizable")


class NestedSchedulePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SchedulePeriod
        fields = ("start", "end", "period")

    period = NestedPeriodSerializer()


class NestedScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Schedule
        fields = ("id", "url", "name", "date", "periods")

    periods = NestedSchedulePeriodSerializer(many=True, read_only=True)
    date = serializers.SerializerMethodField(read_only=True)

    def get_date(self, schedule):
        return self.context.get("date")


# Main


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "type",
            "picture_url",
            "grad_year",
            "is_staff",
            "is_superuser",
            "memberships",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "grad_year":
                field.read_only = True

    memberships = NestedMembershipSerializer(many=True, read_only=True)


class OrganizationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OrganizationLink
        fields = ("title", "url")


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Organization
        fields = (
            "id",
            "url",
            "name",
            "type",
            "advisors",
            "admins",
            "day",
            "time",
            "location",
            "link",
            "ical_links",
            "description",
            "category",
            "links",
        )

    advisors = NestedUserSerializer(many=True, read_only=True)
    admins = NestedUserSerializer(many=True, read_only=True)
    links = OrganizationLinkSerializer(many=True, read_only=True)


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Post
        fields = ("id", "url", "organization", "title", "date", "content", "published")

    organization = NestedOrganizationSerializer(read_only=True)


class PollSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PollSubmission
        fields = ("id", "poll", "user", "responses")

    user = serializers.PrimaryKeyRelatedField(read_only=True)


class PollSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Poll
        fields = ("id", "post", "type", "description", "choices", "min_values", "max_values", "submissions")

    submissions = serializers.SerializerMethodField()

    def get_submissions(self, poll):
        request = self.context.get("request")
        return PollSubmissionSerializer(poll.submissions.filter(user=request.user), many=True).data


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Membership
        fields = ("organization", "points", "points_spent")

    organization = OrganizationSerializer(read_only=True)
    points = serializers.IntegerField(read_only=True)
    points_spent = serializers.IntegerField(read_only=True)


class CreateMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Membership
        fields = ("organization", "points")

    points = serializers.IntegerField(read_only=True)

    @transaction.atomic
    def create(self, validated_data):
        obj, created = self.Meta.model.objects.get_or_create(**validated_data)
        if not created:
            obj.active = True
            obj.save()
        return obj


class ExpoPushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExpoPushToken
        fields = ("token",)

    @transaction.atomic
    def create(self, validated_data):
        obj, _ = self.Meta.model.objects.get_or_create(**validated_data)
        return obj


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Event
        fields = (
            "id",
            "url",
            "organization",
            "name",
            "description",
            "start",
            "end",
            "points",
            "submission_type",
            "claimed",
            "leaderboard",
        )

    organization = NestedOrganizationSerializer(read_only=True)
    claimed = serializers.SerializerMethodField()
    leaderboard = serializers.SerializerMethodField()

    def get_claimed(self, event):
        request = self.context.get("request")
        if request:
            return event.users.filter(id=request.user.id).exists()

    def get_leaderboard(self, event):
        return {
            x["user__grad_year"]: x["count"]
            for x in event.submissions.values("user__grad_year").annotate(count=Count("user__grad_year"))
        }


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Submission
        fields = ("event", "file")

    event = EventSerializer(read_only=True)
    file = serializers.FileField(read_only=True)


class CreateSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Submission
        fields = ("event_id", "event", "file", "code")

    class WrongSubmissionType(Exception):
        pass

    class AlreadyClaimed(Exception):
        pass

    event_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Event.objects.all(), required=False, allow_null=True, write_only=True
    )
    event = EventSerializer(read_only=True)
    file = serializers.FileField(required=False, allow_null=True)
    code = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    @transaction.atomic
    def create(self, validated_data):
        user = validated_data.pop("user")
        code = validated_data.pop("code", None)
        event = validated_data.pop("event_id", None)
        file = validated_data.pop("file", None)

        has_code = code is not None
        has_event = event is not None
        has_file = file is not None
        if not (has_code is not has_event is has_file):
            raise serializers.ValidationError({"code": "Please provide code or both event_id and file."})

        submission_type = models.EventSubmissionType.CODE if has_code else models.EventSubmissionType.FILE
        if submission_type is models.EventSubmissionType.CODE:
            event = models.Event.objects.get(code=code)

        if submission_type != event.submission_type:
            raise self.WrongSubmissionType

        return self.Meta.model.objects.create(event=event, user=user, file=file)


class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Prize
        fields = ("id", "url", "organization", "name", "description", "points")

    organization = NestedOrganizationSerializer(read_only=True)


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Schedule
        fields = ("id", "url", "name", "start", "end", "weekday", "periods", "priority")

    periods = NestedSchedulePeriodSerializer(many=True, read_only=True)
