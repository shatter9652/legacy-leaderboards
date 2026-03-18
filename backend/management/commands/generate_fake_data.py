from django.core.management.base import BaseCommand
from django.db import transaction
import random

from backend.models import (
    Player,
    Leaderboard,
    LeaderboardEntry,
    KillsStats,
    MiningStats,
    FarmingStats,
    TravellingStats,
    StatsType,
)


class Command(BaseCommand):
    help = "Generate fake leaderboard data"

    def add_arguments(self, parser):
        parser.add_argument("--players", type=int, default=100)

    @transaction.atomic
    def handle(self, *args, **options):
        num_players = options["players"]

        self.stdout.write(f"Generating {num_players} players...")

        # Create leaderboards (one per type)
        leaderboards = {}
        for stats_type in StatsType:
            lb, _ = Leaderboard.objects.get_or_create(
                stats_type=stats_type,
                difficulty=1
            )
            leaderboards[stats_type] = lb

        players = []

        # Create players
        for i in range(num_players):
            player = Player.objects.create(
                uid=f"user_{i}",
                name=f"Player {i}"
            )
            players.append(player)

        self.stdout.write("Creating leaderboard entries...")

        # Create entries + stats
        for player in players:
            for stats_type, lb in leaderboards.items():

                score = random.randint(0, 1000)

                entry = LeaderboardEntry.objects.create(
                    player=player,
                    leaderboard=lb,
                    total_score=score,
                    rank=0  # temp
                )

                if stats_type == StatsType.KILLS:
                    KillsStats.objects.create(
                        entry=entry,
                        zombie=random.randint(0, 100),
                        skeleton=random.randint(0, 100),
                        creeper=random.randint(0, 100),
                        spider=random.randint(0, 100),
                        spider_jockey=random.randint(0, 50),
                        zombie_pigman=random.randint(0, 50),
                        slime=random.randint(0, 50),
                    )

                elif stats_type == StatsType.MINING:
                    MiningStats.objects.create(
                        entry=entry,
                        dirt=random.randint(0, 200),
                        stone=random.randint(0, 200),
                        sand=random.randint(0, 200),
                        cobblestone=random.randint(0, 200),
                        gravel=random.randint(0, 200),
                        clay=random.randint(0, 200),
                        obsidian=random.randint(0, 50),
                    )

                elif stats_type == StatsType.FARMING:
                    FarmingStats.objects.create(
                        entry=entry,
                        eggs=random.randint(0, 100),
                        wheat=random.randint(0, 100),
                        mushroom=random.randint(0, 100),
                        sugarcane=random.randint(0, 100),
                        milk=random.randint(0, 100),
                        pumpkin=random.randint(0, 100),
                    )

                elif stats_type == StatsType.TRAVELLING:
                    TravellingStats.objects.create(
                        entry=entry,
                        walked=random.randint(0, 10000),
                        fallen=random.randint(0, 1000),
                        minecart=random.randint(0, 5000),
                        boat=random.randint(0, 5000),
                    )

        self.stdout.write("Calculating ranks...")

        # Recalculate ranks per leaderboard
        for lb in leaderboards.values():
            entries = LeaderboardEntry.objects.filter(
                leaderboard=lb
            ).order_by("-total_score")

            for rank, entry in enumerate(entries, start=1):
                entry.rank = rank
                entry.save(update_fields=["rank"])

        self.stdout.write(self.style.SUCCESS("Done generating fake data!"))