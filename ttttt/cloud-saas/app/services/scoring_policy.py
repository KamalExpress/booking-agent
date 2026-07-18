from datetime import datetime, timezone
from app.models import PortalAccount, Proxy, WorkerNode, Assignment, BookingTask

class ScoringPolicy:
    """
    Centralized math and scoring logic for the scheduler.
    This decoupled class allows tuning how resources are prioritized.
    """

    @staticmethod
    def get_utcnow() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def score_account(account: PortalAccount, task_provider: str) -> int:
        """
        Calculates a priority score for a given PortalAccount.
        Returns a score (higher is better) or -1 if ineligible.
        """
        if account.status != "READY":
            return -1
            
        if account.provider != task_provider:
            return -1
            
        now = ScoringPolicy.get_utcnow()
        if account.cooldown_until and account.cooldown_until > now:
            return -1

        # Base score is the health score
        score = account.health_score

        # Penalty for recent failures
        score -= (account.failure_count * 10)

        # Bonus if it hasn't been used recently (load balancing)
        if account.last_login:
            idle_seconds = (now - account.last_login).total_seconds()
            score += min(int(idle_seconds / 3600), 20) # Up to 20 bonus points for being idle

        return max(score, 0)

    @staticmethod
    def score_proxy(proxy: Proxy) -> int:
        """
        Calculates a priority score for a given Proxy.
        Returns a score (higher is better) or -1 if ineligible.
        """
        if proxy.status != "READY":
            return -1
            
        now = ScoringPolicy.get_utcnow()
        if proxy.cooldown_until and proxy.cooldown_until > now:
            return -1

        # Base score is the health score
        score = proxy.health_score

        # Penalty for failures
        score -= (proxy.failure_count * 5)

        # Bonus for being idle
        if proxy.last_used:
            idle_seconds = (now - proxy.last_used).total_seconds()
            score += min(int(idle_seconds / 1800), 15) # Up to 15 bonus points

        return max(score, 0)

    @staticmethod
    def score_worker_for_scraping(worker: WorkerNode, assignment: Assignment) -> int:
        """
        Evaluates if a worker is fit to execute a given Assignment (scraping).
        Returns a score (higher is better) or -1 if ineligible.
        """
        if not worker.is_online or worker.scheduling_state != "Accepting Jobs":
            return -1
            
        if not worker.can_scrape:
            return -1

        # Simple capability check based on required_labels
        worker_labels = worker.labels or {}
        required_labels = assignment.required_labels or {}
        
        for k, v in required_labels.items():
            if worker_labels.get(k) != v:
                return -1

        # Score based on available concurrency
        if worker.current_concurrency >= worker.max_concurrency:
            return -1

        available_slots = worker.max_concurrency - worker.current_concurrency
        
        return available_slots * 10

    @staticmethod
    def score_worker_for_booking(worker: WorkerNode, booking_task: BookingTask) -> int:
        """
        Evaluates if a worker is fit to execute a BookingTask.
        Returns a score (higher is better) or -1 if ineligible.
        """
        if not worker.is_online or worker.scheduling_state != "Accepting Jobs":
            return -1
            
        if not worker.can_book:
            return -1

        # Score based on available concurrency
        if worker.current_concurrency >= worker.max_concurrency:
            return -1

        available_slots = worker.max_concurrency - worker.current_concurrency
        
        # Bookers should ideally have high performance/premium resources
        # We can add a bonus for being a dedicated booker
        score = available_slots * 20
        if not worker.can_scrape:
            score += 50 # Bonus for dedicated booking nodes

        return score
