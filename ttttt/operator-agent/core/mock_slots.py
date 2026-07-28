import random
import logging
from datetime import datetime, timedelta

class MockSlotGenerator:
    """
    Decoupled generator for mock appointment slots during testing.
    Generates 1-2 available time slots on a random upcoming Sunday within the next 30 days.
    """
    
    @staticmethod
    def get_random_upcoming_sunday() -> str:
        """Calculates a random Sunday within the next 30 days."""
        today = datetime.now()
        # Find all Sundays in the next 30 days (starting at least 3 days from now)
        sundays = []
        for day_offset in range(3, 30):
            candidate = today + timedelta(days=day_offset)
            if candidate.weekday() == 6:  # 6 represents Sunday
                sundays.append(candidate)
                
        if not sundays:
            # Fallback to next Sunday
            days_ahead = 6 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            sundays = [today + timedelta(days=days_ahead)]
            
        selected_sunday = random.choice(sundays)
        return selected_sunday.strftime("%d/%m/%Y")

    @classmethod
    def generate_mock_response(cls, target_date: str = None) -> dict:
        """
        Generates a standard mock slot response.
        If target_date is not provided, a random upcoming Sunday within 30 days is chosen.
        """
        slot_date = target_date if target_date else cls.get_random_upcoming_sunday()
        
        # Available mock times
        possible_times = ["09:00", "10:30", "11:45", "02:00", "03:30"]
        num_slots = random.choice([1, 2])
        selected_times = sorted(random.sample(possible_times, k=num_slots))
        
        mock_slots = []
        for start_time in selected_times:
            mock_slots.append({
                "isavailable": True,
                "isselectable": True,
                "starttime": start_time,
                "date": slot_date
            })
            
        logging.info(f"[MockSlotGenerator] Generated {len(mock_slots)} mock slot(s) for date {slot_date}: {selected_times}")
        
        return {
            "code": "SUCCESS",
            "returnobject": {
                "slots": mock_slots
            }
        }
