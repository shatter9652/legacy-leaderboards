from django.urls import path
from .views import (
    AddAchievementToPlayerView,
    AchievementsUIView,
    AchievementListView,
    ApiRootView,
    CreatePlayerView,
    PlayerDetailsView,
    RemoveAchievementFromPlayerView,
    WriteStatsView,
    TopRankView,
    FriendsLeaderboardView,
    MyScoreView,
    LeaderboardView,
)

urlpatterns = [
    path("ui/achievements", AchievementsUIView.as_view()),
    path("api/", ApiRootView.as_view()),
    path("api/achievement/list", AchievementListView.as_view()),
    path("api/achievement/add", AddAchievementToPlayerView.as_view()),
    path("api/achievement/remove", RemoveAchievementFromPlayerView.as_view()),
    path("api/player", PlayerDetailsView.as_view()),
    path("api/player/add", CreatePlayerView.as_view()),
    path("api/leaderboard/write/", WriteStatsView.as_view()),
    path("api/leaderboard/top/", TopRankView.as_view()),
    path("api/leaderboard/friends/", FriendsLeaderboardView.as_view()),
    path("api/leaderboard/my-score/", MyScoreView.as_view()),
]