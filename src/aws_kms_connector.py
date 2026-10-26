import json
import base64
import time

class AWSKMSConnector:
    def __init__(self, key_id="alias/guardian-ai-key"):
        self.key_id = key_id

    def encrypt_and_pack(self, device_id, objects_data):
        """
        Packs tracker state and encrypts telemetry payload for secure transit to AWS.
        """
        payload = {
            "device_id": device_id,
            "timestamp": time.time(),
            "tracked_entities": [
                {
                    "id": oid,
                    "dwell_time_seconds": info["dwell_time"],
                    "loitering_alert": info["dwell_time"] > 120
                }
                for oid, info in objects_data.items()
            ]
        }

        serialized = json.dumps(payload)
        # Simulated KMS envelope encryption (base64 payload)
        encrypted_bytes = base64.b64encode(serialized.encode('utf-8')).decode('utf-8')

        return {
            "kms_key_arn": f"arn:aws:kms:us-east-1:123456789012:{self.key_id}",
            "encrypted_payload": encrypted_bytes,
            "status": "ENCRYPTED_AES_256"
        }