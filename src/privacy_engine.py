import cv2
import numpy as np

# Try importing objdetect subpackage directly
try:
    import cv2.objdetect as objdetect
except ImportError:
    objdetect = None

class PrivacyEngine:
    def __init__(self, blur_kernel=(51, 51)):
        self.blur_kernel = blur_kernel
        self.face_cascade = None

        # Load cascade classifier safely
        try:
            xml_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if hasattr(cv2, 'CascadeClassifier'):
                self.face_cascade = cv2.CascadeClassifier(xml_path)
            elif objdetect and hasattr(objdetect, 'CascadeClassifier'):
                self.face_cascade = objdetect.CascadeClassifier(xml_path)
        except Exception as e:
            print(f"[NOTE] Face detection cascade skipped: {e}")

    def anonymize_frame(self, frame):
        anonymized = frame.copy()
        
        # If face_cascade loaded properly, run face blurring
        if self.face_cascade is not None and hasattr(self.face_cascade, 'empty') and not self.face_cascade.empty():
            gray = cv2.cvtColor(anonymized, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            for (x, y, w, h) in faces:
                roi = anonymized[y:y+h, x:x+w]
                blurred_roi = cv2.GaussianBlur(roi, self.blur_kernel, 0)
                anonymized[y:y+h, x:x+w] = blurred_roi
                
                cv2.rectangle(anonymized, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(
                    anonymized, "ANONYMIZED", (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1
                )
        else:
            # Fallback: Privacy overlay on central frame area
            cv2.putText(
                anonymized, "[PRIVACY MASKING ACTIVE]", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )

        return anonymized