"""Leaderboard ranking and statistics"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class LeaderboardCalculator:
    """Calculate leaderboard rankings and ratings"""
    
    @staticmethod
    def calculate_user_stats(
        accepted_problems: int,
        total_submissions: int,
        total_runtime_ms: int,
        problems: int = 0,
    ) -> Dict[str, float]:
        """
        Calculate comprehensive user statistics
        
        Args:
            accepted_problems: Number of accepted submissions
            total_submissions: Total number of submissions
            total_runtime_ms: Sum of all runtimes
            problems: Number of unique problems attempted
        
        Returns:
            Statistics dictionary
        """
        if total_submissions == 0:
            return {
                "acceptance_rate": 0.0,
                "average_attempts": 0.0,
                "average_runtime_ms": 0,
                "efficiency_score": 0.0,
            }
        
        acceptance_rate = (accepted_problems / total_submissions) * 100
        average_attempts = total_submissions / accepted_problems if accepted_problems > 0 else 0
        average_runtime_ms = total_runtime_ms // total_submissions if total_submissions > 0 else 0
        
        # Efficiency score: higher acceptance rate + fewer attempts + faster runtime
        efficiency_score = (
            (acceptance_rate * 0.4) +
            ((100 - min(average_attempts, 100) * 10) * 0.3) +  # penalize many attempts
            ((1000 - min(average_runtime_ms, 1000)) / 10 * 0.3)  # penalize slow solutions
        )
        
        return {
            "acceptance_rate": round(acceptance_rate, 2),
            "average_attempts": round(average_attempts, 2),
            "average_runtime_ms": average_runtime_ms,
            "efficiency_score": round(efficiency_score, 2),
        }
    
    @staticmethod
    def calculate_elo_rating(
        current_rating: int = 1200,
        opponent_rating: int = 1200,
        win: bool = True,
        k_factor: int = 32,
    ) -> int:
        """
        Calculate ELO rating change (Codeforces style)
        
        Args:
            current_rating: Current user rating
            opponent_rating: Opponent/average rating
            win: Whether user won/accepted
            k_factor: Rating volatility factor
        
        Returns:
            New rating
        """
        expected_score = 1 / (1 + 10 ** ((opponent_rating - current_rating) / 400))
        actual_score = 1.0 if win else 0.0
        rating_change = k_factor * (actual_score - expected_score)
        
        return max(0, int(current_rating + rating_change))
    
    @staticmethod
    def rank_users(
        users: List[Dict],
        ranking_by: str = "accepted",
    ) -> List[Tuple[int, Dict]]:
        """
        Rank users for leaderboard
        
        Args:
            users: List of user dicts with stats
            ranking_by: Ranking criterion (accepted, rating, efficiency)
        
        Returns:
            List of (rank, user_dict) tuples
        """
        if ranking_by == "accepted":
            sorted_users = sorted(
                users,
                key=lambda u: (-u.get("accepted_count", 0), u.get("submission_count", 0))
            )
        elif ranking_by == "rating":
            sorted_users = sorted(
                users,
                key=lambda u: -u.get("rating", 1200)
            )
        elif ranking_by == "efficiency":
            sorted_users = sorted(
                users,
                key=lambda u: -u.get("efficiency_score", 0.0)
            )
        else:
            sorted_users = users
        
        ranked = [(i + 1, user) for i, user in enumerate(sorted_users)]
        return ranked
    
    @staticmethod
    def calculate_problem_stats(
        total_submissions: int,
        accepted_count: int,
        average_runtime_ms: int = 0,
    ) -> Dict[str, float]:
        """
        Calculate problem statistics
        
        Args:
            total_submissions: Total attempts
            accepted_count: Number of accepted solutions
            average_runtime_ms: Average runtime
        
        Returns:
            Stats dictionary
        """
        acceptance_rate = (accepted_count / total_submissions * 100) if total_submissions > 0 else 0
        
        return {
            "total_submissions": total_submissions,
            "accepted_count": accepted_count,
            "acceptance_rate": round(acceptance_rate, 2),
            "average_runtime_ms": average_runtime_ms,
            "difficulty_rating": LeaderboardCalculator._calculate_difficulty_rating(
                acceptance_rate, total_submissions
            ),
        }
    
    @staticmethod
    def _calculate_difficulty_rating(acceptance_rate: float, submissions: int) -> float:
        """
        Calculate a difficulty rating based on acceptance rate
        
        Ranges from 0 (trivial) to 100+ (extremely hard)
        """
        # Lower acceptance = higher difficulty
        if acceptance_rate >= 90:
            base_difficulty = 10
        elif acceptance_rate >= 70:
            base_difficulty = 30
        elif acceptance_rate >= 50:
            base_difficulty = 50
        elif acceptance_rate >= 30:
            base_difficulty = 70
        else:
            base_difficulty = 90
        
        # Adjust based on submission count (more submissions = slightly higher difficulty)
        if submissions > 1000:
            base_difficulty += 10
        elif submissions > 500:
            base_difficulty += 5
        
        return round(base_difficulty, 1)
    
    @staticmethod
    def get_user_streak(
        recent_submissions: List[Dict],
        days: int = 7,
    ) -> int:
        """
        Calculate user's current streak (consecutive accepted problems)
        
        Args:
            recent_submissions: Recent submission history
            days: Time window
        
        Returns:
            Current streak count
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        
        # Filter accepted submissions in time window
        accepted = [
            s for s in recent_submissions
            if s.get("verdict") == "accepted" and
            datetime.fromisoformat(s.get("submitted_at", "")) > cutoff
        ]
        
        # Sort by date descending
        accepted.sort(key=lambda s: s.get("submitted_at", ""), reverse=True)
        
        if not accepted:
            return 0
        
        # Count consecutive days with accepts
        streak = 1
        for i in range(1, len(accepted)):
            curr = datetime.fromisoformat(accepted[i - 1]["submitted_at"])
            prev = datetime.fromisoformat(accepted[i]["submitted_at"])
            
            days_diff = (curr - prev).days
            if days_diff == 1:
                streak += 1
            elif days_diff > 1:
                break
        
        return streak


def get_global_leaderboard(
    db_session,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """
    Get global leaderboard
    
    Args:
        db_session: Database session
        limit: Number of entries
        offset: Pagination offset
    
    Returns:
        List of leaderboard entries
    """
    try:
        # TODO: Implement with database query
        # SELECT users.*, COUNT(DISTINCT submissions.problem_id) as accepted_count,
        #        COUNT(submissions.id) as submission_count,
        #        SUM(submissions.runtime_ms) as total_runtime_ms
        # FROM users
        # LEFT JOIN submissions ON users.id = submissions.user_id AND submissions.verdict = 'accepted'
        # GROUP BY users.id
        # ORDER BY accepted_count DESC, submission_count ASC
        # LIMIT :limit OFFSET :offset
        
        return []
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return []


def get_problem_leaderboard(
    db_session,
    problem_id: int,
    limit: int = 50,
) -> List[Dict]:
    """Get leaderboard for a specific problem"""
    try:
        # TODO: Implement with database query
        # Get fastest/best accepted solutions for problem
        return []
    except Exception as e:
        logger.error(f"Error getting problem leaderboard: {e}")
        return []
