class AgentOrchestrator:
    def __init__(self, dwell_threshold=120):
        self.dwell_threshold = dwell_threshold

    def evaluate_and_act(self, tracker_objects):
        actions_taken = []

        for oid, data in tracker_objects.items():
            dwell = data["dwell_time"]

            if dwell > self.dwell_threshold:
                actions_taken.append({
                    "target_id": oid,
                    "trigger": "LOITERING_THRESHOLD_EXCEEDED",
                    "actions": [
                        "ADAPTIVE_ZOOM_ROI_LOCK",
                        "SECURITY_GUARD_PUSH_NOTIFICATION",
                        "LOCAL_SIREN_TRIGGER"
                    ]
                })

        return actions_taken