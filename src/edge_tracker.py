import numpy as np
import time

class CentroidTracker:
    def __init__(self, max_disappeared=40, loitering_limit=120):
        self.next_object_id = 0
        self.objects = {}         # ID -> {"centroid": (x,y), "start_time": t, "last_seen": t, "dwell_time": t}
        self.disappeared = {}     # ID -> count
        self.max_disappeared = max_disappeared
        self.loitering_limit = loitering_limit

    def register(self, centroid):
        current_time = time.time()
        self.objects[self.next_object_id] = {
            "centroid": centroid,
            "start_time": current_time,
            "last_seen": current_time,
            "dwell_time": 0.0
        }
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, rects):
        current_time = time.time()

        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for (i, (startX, startY, endX, endY)) in enumerate(rects):
            input_centroids[i] = (int((startX + endX) / 2.0), int((startY + endY) / 2.0))

        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = np.array([self.objects[oid]["centroid"] for oid in object_ids])

            D = np.linalg.norm(object_centroids[:, np.newaxis] - input_centroids, axis=2)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows, used_cols = set(), set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                object_id = object_ids[row]
                self.objects[object_id]["centroid"] = input_centroids[col]
                self.objects[object_id]["last_seen"] = current_time
                self.objects[object_id]["dwell_time"] = round(current_time - self.objects[object_id]["start_time"], 2)
                self.disappeared[object_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            for row in set(range(D.shape[0])).difference(used_rows):
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            for col in set(range(D.shape[1])).difference(used_cols):
                self.register(input_centroids[col])

        return self.objects