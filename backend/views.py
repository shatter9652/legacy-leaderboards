from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import URLPattern, URLResolver, get_resolver
from django.views import View
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Achievement, Player, PlayerAchievement, Leaderboard, LeaderboardEntry, StatsType, DifficultyType
from .serializers import (
    AddAchievementToPlayerSerializer,
    AchievementSerializer,
    CreatePlayerSerializer,
    LeaderboardEntrySerializer,
    PlayerDetailsSerializer,
    PlayerSerializer,
    RegisterScoreSerializer,
)


class CreateAccountView(View):
    template_name = "backend/auth_form.html"

    def get(self, request):
        uid = request.GET.get("uid", "").strip()
        return render(
            request,
            self.template_name,
            {
                "page_title": "Create Account",
                "heading": "Create Account",
                "subheading": "Start tracking your progress",
                "button_text": "Create Account",
                "mode": "register",
                "uid": uid,
            },
        )

    def post(self, request):
        username = request.POST.get("username", "").strip()
        uid = request.POST.get("uid", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        context = {
            "page_title": "Create Account",
            "heading": "Create Account",
            "subheading": "Start tracking your progress",
            "button_text": "Create Account",
            "mode": "register",
            "username": username,
            "uid": uid,
        }

        if not username or not uid or not password:
            context["error"] = "Username, UID, and password are required."
            return render(request, self.template_name, context, status=400)

        if password != confirm_password:
            context["error"] = "Passwords do not match."
            return render(request, self.template_name, context, status=400)

        if User.objects.filter(username=username).exists():
            context["error"] = "That username is already taken."
            return render(request, self.template_name, context, status=400)

        with transaction.atomic():
            existing_player = Player.objects.select_for_update().filter(uid=uid).first()
            if existing_player and existing_player.user_id is not None:
                context["error"] = "That UID is already linked to another account."
                return render(request, self.template_name, context, status=400)

            user = User.objects.create_user(username=username, password=password)

            if existing_player:
                existing_player.user = user
                existing_player.save(update_fields=["user"])
            else:
                Player.objects.create(user=user, uid=uid, name=username)

        return redirect("login")


class LoginView(View):
    template_name = "backend/auth_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "page_title": "Login",
                "heading": "Login",
                "subheading": "Welcome back",
                "button_text": "Login",
                "mode": "login",
            },
        )

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        context = {
            "page_title": "Login",
            "heading": "Login",
            "subheading": "Welcome back",
            "button_text": "Login",
            "mode": "login",
            "username": username,
        }

        if not username or not password:
            context["error"] = "Username and password are required."
            return render(request, self.template_name, context, status=400)

        user = authenticate(request, username=username, password=password)
        if user is None:
            context["error"] = "Invalid username or password."
            return render(request, self.template_name, context, status=401)

        auth_login(request, user)

        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        context["success"] = f"You are now logged in as {user.username}."
        return render(request, self.template_name, context)


class LogoutView(View):
    def get(self, request):
        auth_logout(request)
        return redirect("login")

    def post(self, request):
        auth_logout(request)
        return redirect("login")


class MyAchievementsRedirectView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")

        player = Player.objects.filter(user=request.user).only("uid").first()
        if player is None:
            return redirect("create-account")

        return redirect(f"/ui/achievements?uid={player.uid}")


class ApiRootView(APIView):
    def _iter_urlpatterns(self, patterns, prefix=""):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                nested_prefix = f"{prefix}{pattern.pattern}"
                yield from self._iter_urlpatterns(pattern.url_patterns, nested_prefix)
            elif isinstance(pattern, URLPattern):
                route = f"{prefix}{pattern.pattern}".lstrip("/")
                yield route, pattern.callback

    def _extract_operations(self, callback):
        view_class = getattr(callback, "view_class", None)
        if view_class is None:
            return []

        ops = []
        for method in getattr(view_class, "http_method_names", []):
            if method in {"head", "options", "trace"}:
                continue
            if hasattr(view_class, method):
                ops.append(method.upper())
        return ops

    def get(self, request):
        base_url = request.build_absolute_uri("/").rstrip("/")
        endpoints = []

        for route, callback in self._iter_urlpatterns(get_resolver().url_patterns):
            normalized = route.strip("^").strip("$")
            if not normalized.startswith("api/"):
                continue

            if normalized == "api/":
                continue

            operations = self._extract_operations(callback)
            if not operations:
                continue

            endpoints.append(
                {
                    "path": f"{base_url}/{normalized}",
                    "operations": operations,
                }
            )

        endpoints.sort(key=lambda item: item["path"])

        return Response(
            {
                "name": "Legacy Leaderboards API",
                "path": f"{base_url}/api/",
                "operations": ["GET"],
                "endpoints": endpoints,
            }
        )


class AchievementsUIView(APIView):
    def _build_icon_map(self):
        icon_map = {}
        icons_dir = Path(settings.MEDIA_ROOT) / "achievements"
        if not icons_dir.exists():
            return icon_map

        for icon_file in sorted(icons_dir.glob("MCTrophy_*.png")):
            try:
                achievement_id = int(icon_file.stem.split("_")[-1])
            except ValueError:
                continue
            icon_map[achievement_id] = f"{settings.MEDIA_URL}achievements/{icon_file.name}"

        return icon_map

    def get(self, request):
        uid = request.query_params.get("uid")
        if not uid:
            return Response({"error": "Missing required query param: uid"}, status=400)

        if not request.user.is_authenticated:
            create_account_url = f"{reverse('create-account')}?uid={uid}"
            return redirect(create_account_url)

        try:
            player = Player.objects.get(uid=uid)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=404)

        icon_map = self._build_icon_map()
        unlocked_ids = set(
            PlayerAchievement.objects.filter(player=player, status=True)
            .values_list("achievement_id", flat=True)
        )

        current_score = PlayerAchievement.objects.filter(player=player, status=True).aggregate(score=Sum("achievement__score"))["score"] or 0
        total_score = Achievement.objects.aggregate(total_score=Sum("score"))["total_score"] or 0

        cards = []
        for achievement_id, icon_url in sorted(icon_map.items()):
            achievement = Achievement.objects.filter(id=achievement_id).first()
            cards.append(
                {
                    "id": achievement_id,
                    "name": achievement.name if achievement else f"Achievement {achievement_id}",
                    "description": achievement.description if achievement else "No description available.",
                    "score": achievement.score if achievement else 0,
                    "icon_url": icon_url,
                    "is_unlocked": achievement_id in unlocked_ids,
                }
            )

        context = {
            "name": player.name,
            "uid": uid,
            "cards": cards,
            "unlocked_count": sum(1 for card in cards if card["is_unlocked"]),
            "total_count": len(cards),
            "current_score": current_score,
            "total_score": total_score,
        }
        return render(request, "backend/achievements_ui.html", context)

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


def get_leaderboard_from_query_params(request):
    difficulty_key = str(request.query_params.get("difficulty", "")).lower()
    type_key = str(request.query_params.get("type", "")).lower()

    if not difficulty_key or not type_key:
        return None, Response(
            {
                "error": "Missing required query params: difficulty, type",
                "allowed_difficulty": list(DIFFICULTY_MAP.keys()),
                "allowed_type": list(TYPE_MAP.keys()),
            },
            status=400,
        )

    if difficulty_key not in DIFFICULTY_MAP:
        return None, Response(
            {
                "error": "Invalid difficulty",
                "allowed_difficulty": list(DIFFICULTY_MAP.keys()),
            },
            status=400,
        )

    if type_key not in TYPE_MAP:
        return None, Response(
            {
                "error": "Invalid type",
                "allowed_type": list(TYPE_MAP.keys()),
            },
            status=400,
        )

    difficulty = DIFFICULTY_MAP[difficulty_key]
    stats_type = TYPE_MAP[type_key]

    try:
        leaderboard = Leaderboard.objects.get(
            difficulty=difficulty,
            stats_type=stats_type,
        )
    except Leaderboard.DoesNotExist:
        return None, Response(
            {
                "error": "Leaderboard not found for provided difficulty and type"
            },
            status=404,
        )

    return leaderboard, None

class WriteStatsView(APIView):
    def post(self, request):
        serializer = RegisterScoreSerializer(data=request.data)

        if serializer.is_valid():
            entry = serializer.save()
            response_status = (
                status.HTTP_201_CREATED
                if getattr(serializer, "was_created", False)
                else status.HTTP_200_OK
            )

            return Response(
                LeaderboardEntrySerializer(entry).data,
                status=response_status
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class TopRankView(APIView):
    def get(self, request):
        leaderboard, error_response = get_leaderboard_from_query_params(request)
        if error_response:
            return error_response

        start = int(request.query_params.get("start", 0))
        count = int(request.query_params.get("count", 10))

        entries = LeaderboardEntry.objects.filter(
            leaderboard=leaderboard
        ).order_by("rank")[start:start + count]

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)
    
class FriendsLeaderboardView(APIView):
    def get(self, request):
        uid = request.query_params.get("user_id")
        leaderboard, error_response = get_leaderboard_from_query_params(request)
        if error_response:
            return error_response

        try:
            player = Player.objects.get(uid=uid)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=404)

        friends = player.friends.all()

        entries = LeaderboardEntry.objects.filter(
            leaderboard=leaderboard,
            player__in=friends
        ).order_by("rank")

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)
    
class MyScoreView(APIView):
    def get(self, request):
        uid = request.query_params.get("user_id")
        leaderboard, error_response = get_leaderboard_from_query_params(request)
        if error_response:
            return error_response

        count = int(request.query_params.get("count", 5))

        try:
            player = Player.objects.get(uid=uid)
            entry = LeaderboardEntry.objects.get(
                player=player,
                leaderboard=leaderboard
            )
        except (Player.DoesNotExist, LeaderboardEntry.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        start_rank = 1
        end_rank = entry.rank + count

        entries = LeaderboardEntry.objects.filter(
            leaderboard=leaderboard,
            rank__gte=start_rank,
            rank__lte=end_rank
        ).order_by("rank")

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)
    
class LeaderboardView(APIView):
    def get(self, request):
        mode = int(request.query_params.get("mode"))

        if mode == 0:  # Friends
            return FriendsLeaderboardView().get(request)

        elif mode == 1:  # My Score
            return MyScoreView().get(request)

        elif mode == 2:  # Top Rank
            return TopRankView().get(request)

        return Response({"error": "Invalid mode"}, status=400)


class CreatePlayerView(generics.GenericAPIView):
    serializer_class = CreatePlayerSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        player = serializer.save()
        return Response(PlayerSerializer(player).data, status=status.HTTP_201_CREATED)


class PlayerDetailsView(APIView):
    def get(self, request):
        uid = request.query_params.get("uid")
        if not uid:
            return Response({"error": "Missing required query param: uid"}, status=400)

        try:
            player = Player.objects.prefetch_related(
                "leaderboardentry_set__leaderboard",
                "playerachievement_set__achievement",
            ).get(uid=uid)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=404)

        return Response(PlayerDetailsSerializer(player).data)


class AddAchievementToPlayerView(generics.GenericAPIView):
    serializer_class = AddAchievementToPlayerSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        achievement_id = serializer.validated_data["achievement_id"]
        player_uid = serializer.validated_data["player_uid"]

        try:
            player = Player.objects.get(uid=player_uid)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=404)

        try:
            achievement = Achievement.objects.get(id=achievement_id)
        except Achievement.DoesNotExist:
            return Response({"error": "Achievement not found"}, status=404)

        player_achievement, _ = PlayerAchievement.objects.get_or_create(
            player=player,
            achievement=achievement,
            defaults={"status": False},
        )

        if not player_achievement.status:
            player_achievement.status = True
            player_achievement.save(update_fields=["status"])

        return Response(
            {
                "player_uid": player.uid,
                "achievement_id": achievement.id,
                "status": player_achievement.status,
            }
        )


class RemoveAchievementFromPlayerView(generics.GenericAPIView):
    serializer_class = AddAchievementToPlayerSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        achievement_id = serializer.validated_data["achievement_id"]
        player_uid = serializer.validated_data["player_uid"]

        try:
            player = Player.objects.get(uid=player_uid)
        except Player.DoesNotExist:
            return Response({"error": "Player not found"}, status=404)

        try:
            achievement = Achievement.objects.get(id=achievement_id)
        except Achievement.DoesNotExist:
            return Response({"error": "Achievement not found"}, status=404)

        player_achievement, _ = PlayerAchievement.objects.get_or_create(
            player=player,
            achievement=achievement,
            defaults={"status": False},
        )

        if player_achievement.status:
            player_achievement.status = False
            player_achievement.save(update_fields=["status"])

        return Response(
            {
                "player_uid": player.uid,
                "achievement_id": achievement.id,
                "status": player_achievement.status,
            }
        )


class AchievementListView(APIView):
    def get(self, request):
        achievements = Achievement.objects.all().order_by("id")
        serializer = AchievementSerializer(achievements, many=True)
        return Response(serializer.data)