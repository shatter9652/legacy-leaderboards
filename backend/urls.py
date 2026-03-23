from django.urls import path, re_path
from .views import (
    AddAchievementToPlayerView,
    AchievementsUIView,
    AchievementListView,
    ApiRootView,
    CreatePlayerView,
    CreateAccountView,
    LoginView,
    LogoutView,
    MyAchievementsRedirectView,
    PlayerDetailsView,
    RemoveAchievementFromPlayerView,
    WriteStatsView,
    TopRankView,
    FriendsLeaderboardView,
    MyScoreView,
    LeaderboardView,
)

urlpatterns = [
    path("", LoginView.as_view(), name="home"),
    path("my-achievements/", MyAchievementsRedirectView.as_view(), name="my-achievements"),
    path("create-account/", CreateAccountView.as_view(), name="create-account"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("ui/achievements", AchievementsUIView.as_view(), name="achievements-ui"),

    # API ROOT
    re_path(r"^api/?$", ApiRootView.as_view()),

    # ACHIEVEMENTS
    re_path(r"^api/achievement/list/?$", AchievementListView.as_view()),
    re_path(r"^api/achievement/add/?$", AddAchievementToPlayerView.as_view()),
    re_path(r"^api/achievement/remove/?$", RemoveAchievementFromPlayerView.as_view()),

    # PLAYER
    re_path(r"^api/player/?$", PlayerDetailsView.as_view()),
    re_path(r"^api/player/add/?$", CreatePlayerView.as_view()),

    # (OPTIONAL: if you re-enable these later)
    re_path(r"^api/leaderboard/write/?$", WriteStatsView.as_view()),
    re_path(r"^api/leaderboard/top/?$", TopRankView.as_view()),
    re_path(r"^api/leaderboard/friends/?$", FriendsLeaderboardView.as_view()),
    re_path(r"^api/leaderboard/my-score/?$", MyScoreView.as_view()),
]
