from django.urls import path
from .views import (
    ApiRootView,
    WriteStatsView,
    TopRankView,
    FriendsLeaderboardView,
    MyScoreView,
    LeaderboardView,
)

urlpatterns = [
    path("api/", ApiRootView.as_view()),
    path("api/leaderboard/write/", WriteStatsView.as_view()),
    path("api/leaderboard/top/", TopRankView.as_view()),
    path("api/leaderboard/friends/", FriendsLeaderboardView.as_view()),
    path("api/leaderboard/my-score/", MyScoreView.as_view()),
]