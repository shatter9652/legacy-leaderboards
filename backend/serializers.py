from rest_framework import serializers
from .models import (
    Achievement,
    Player,
    PlayerAchievement,
    Leaderboard,
    LeaderboardEntry,
    KillsStats,
    MiningStats,
    FarmingStats,
    TravellingStats,
)

class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ["id", "uid", "name"]

class KillsStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = KillsStats
        exclude = ["id", "entry"]


class MiningStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiningStats
        exclude = ["id", "entry"]


class FarmingStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmingStats
        exclude = ["id", "entry"]


class TravellingStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravellingStats
        exclude = ["id", "entry"]

from .models import StatsType, DifficultyType

class StatsDataSerializer(serializers.Serializer):
    type = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    def get_type(self, obj):
        return obj.leaderboard.get_stats_type_display()

    def get_data(self, obj):
        if hasattr(obj, "kills"):
            return KillsStatsSerializer(obj.kills).data
        if hasattr(obj, "mining"):
            return MiningStatsSerializer(obj.mining).data
        if hasattr(obj, "farming"):
            return FarmingStatsSerializer(obj.farming).data
        if hasattr(obj, "travelling"):
            return TravellingStatsSerializer(obj.travelling).data
        return None
    

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = [
            "player",
            "rank",
            "total_score",
            "stats",
        ]

    def get_stats(self, obj):
        return StatsDataSerializer(obj).data


class PlayerStatsEntrySerializer(serializers.ModelSerializer):
    stats_type = serializers.SerializerMethodField()
    difficulty = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = [
            "stats_type",
            "difficulty",
            "rank",
            "total_score",
            "stats",
        ]

    def get_stats_type(self, obj):
        return obj.leaderboard.get_stats_type_display()

    def get_difficulty(self, obj):
        return obj.leaderboard.get_difficulty_display()

    def get_stats(self, obj):
        return StatsDataSerializer(obj).data["data"]


class PlayerAchievementSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="achievement.id", read_only=True)
    name = serializers.CharField(source="achievement.name", read_only=True)
    description = serializers.CharField(source="achievement.description", read_only=True)
    score = serializers.IntegerField(source="achievement.score", read_only=True)

    class Meta:
        model = PlayerAchievement
        fields = [
            "id",
            "name",
            "description",
            "score",
            "status",
        ]


class PlayerDetailsSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()
    achievements = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ["id", "uid", "name", "stats", "achievements"]

    def get_stats(self, obj):
        entries = obj.leaderboardentry_set.all().order_by("leaderboard__difficulty", "leaderboard__stats_type")
        return PlayerStatsEntrySerializer(entries, many=True).data

    def get_achievements(self, obj):
        player_achievements = obj.playerachievement_set.all().order_by("achievement__id")
        return PlayerAchievementSerializer(player_achievements, many=True).data
    
class RegisterScoreSerializer(serializers.Serializer):
    player_uid = serializers.CharField()
    difficulty = serializers.CharField()
    type = serializers.CharField()
    score = serializers.IntegerField()
    stats = serializers.DictField()

    DIFFICULTY_MAP = {
        "peaceful": DifficultyType.PEACEFUL,
        "easy": DifficultyType.EASY,
        "normal": DifficultyType.NORMAL,
        "hard": DifficultyType.HARD,
    }

    TYPE_MAP = {
        "travelling": StatsType.TRAVELLING,
        "mining": StatsType.MINING,
        "farming": StatsType.FARMING,
        "kills": StatsType.KILLS,
    }

    def create(self, validated_data):
        player, _ = Player.objects.get_or_create(
            uid=validated_data["player_uid"]
        )

        difficulty_key = str(validated_data["difficulty"]).lower()
        type_key = str(validated_data["type"]).lower()

        try:
            difficulty = self.DIFFICULTY_MAP[difficulty_key]
        except KeyError as exc:
            allowed = ", ".join(self.DIFFICULTY_MAP.keys())
            raise serializers.ValidationError(
                {"difficulty": f"Invalid difficulty. Allowed values: {allowed}"}
            ) from exc

        try:
            stats_type = self.TYPE_MAP[type_key]
        except KeyError as exc:
            allowed = ", ".join(self.TYPE_MAP.keys())
            raise serializers.ValidationError(
                {"type": f"Invalid type. Allowed values: {allowed}"}
            ) from exc

        leaderboard, _ = Leaderboard.objects.get_or_create(
            stats_type=stats_type,
            difficulty=difficulty,
        )

        entry = LeaderboardEntry.objects.create(
            player=player,
            leaderboard=leaderboard,
            total_score=validated_data["score"],
            rank=0,  # compute later
        )

        stats = validated_data["stats"]

        if stats_type == StatsType.KILLS:
            KillsStats.objects.create(entry=entry, **stats)

        elif stats_type == StatsType.MINING:
            MiningStats.objects.create(entry=entry, **stats)

        elif stats_type == StatsType.FARMING:
            FarmingStats.objects.create(entry=entry, **stats)

        elif stats_type == StatsType.TRAVELLING:
            TravellingStats.objects.create(entry=entry, **stats)

        return entry


class CreatePlayerSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=255)

    def validate_uid(self, value):
        if Player.objects.filter(uid=value).exists():
            raise serializers.ValidationError("A player with this uid already exists.")
        return value

    def create(self, validated_data):
        return Player.objects.create(
            uid=validated_data["uid"],
            name=validated_data["name"],
        )


class AddAchievementToPlayerSerializer(serializers.Serializer):
    achievement_id = serializers.IntegerField()
    player_uid = serializers.CharField(max_length=64)


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ["id", "name", "description", "score"]
    
class LeaderboardSerializer(serializers.ModelSerializer):
    entries = LeaderboardEntrySerializer(
        source="leaderboardentry_set",
        many=True,
        read_only=True
    )

    class Meta:
        model = Leaderboard
        fields = [
            "id",
            "stats_type",
            "difficulty",
            "entries",
        ]