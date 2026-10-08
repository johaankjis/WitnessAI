import pytest

from witness_vision.config import VisionConfig
from witness_vision.measurements import (
    estimate_signal_color,
    lateral_shifts,
    localize_event,
    scale_changes,
    summarize_signal,
)
from witness_vision.tracking import IoUTracker
from witness_vision.types import Box, Detection, Track, VideoMeta


def det(i, label="car", box=(0, 0, 10, 10), conf=0.9, fps=10.0):
    return Detection(i, i / fps, label, conf, Box(*box))


def test_tracker_keeps_ids_across_frames_and_labels():
    tracker = IoUTracker(iou_match=0.3, max_gap_seconds=1.0)
    for i in range(5):
        tracker.update([det(i, "car", (10 + i, 10, 50 + i, 40)), det(i, "traffic light", (10 + i, 10, 50 + i, 40)),
                        det(i, "truck", (200, 10, 260, 60))])
    tracks = tracker.tracks()
    assert [(t.track_id, t.label, len(t.detections)) for t in tracks] == [(1, "car", 5), (2, "traffic light", 5),
                                                                          (3, "truck", 5)]


def test_tracker_gap_starts_new_track_and_min_hits_filters_without_renumbering():
    tracker = IoUTracker(max_gap_seconds=0.5)
    tracker.update([det(0, box=(100, 100, 120, 120))])          # id 1, single hit
    for i in range(1, 4):
        tracker.update([det(i, box=(0, 0, 10, 10))])             # id 2
    tracker.update([det(20, box=(0, 0, 10, 10))])                # 1.6 s later -> id 3
    assert [t.track_id for t in tracker.tracks()] == [1, 2, 3]
    assert [t.track_id for t in tracker.tracks(min_hits=2)] == [2]


def test_tracker_deterministic_under_input_order():
    a, b = det(0, box=(0, 0, 10, 10), conf=0.5), det(0, box=(100, 0, 110, 10), conf=0.9)
    t1, t2 = IoUTracker(), IoUTracker()
    t1.update([a, b])
    t2.update([b, a])
    assert [t.detections for t in t1.tracks()] == [t.detections for t in t2.tracks()]


META = VideoMeta("x", 10.0, 100, 640, 360)


def growing_track(track_id=1, start_frame=0, frames=20, growth_start=10):
    track = Track(track_id, "car")
    for i in range(start_frame, start_frame + frames):
        s = 40 if i < growth_start else 40 * (1.25 ** (i - growth_start))
        track.detections.append(det(i, box=(300, 200, 300 + s, 200 + s * 0.6)))
    return track


def test_localize_event_finds_growth_and_clips_window():
    event = localize_event([growing_track()], META, VisionConfig())
    assert event is not None and event.track_id == 1
    assert 1.0 <= event.timestamp_seconds <= 1.3
    assert event.frame_index == round(event.timestamp_seconds * 10)
    assert event.window_start == pytest.approx(max(0.0, event.timestamp_seconds - 2.0))
    assert event.window_end <= META.duration_seconds


def test_static_or_tiny_objects_produce_no_event():
    static = Track(1, "car", [det(i, box=(300, 200, 340, 230)) for i in range(20)])
    assert localize_event([static], META, VisionConfig()) is None
    tiny = Track(2, "car", [det(i, box=(0, 0, 2 + i * 0.5, 2 + i * 0.5)) for i in range(20)])
    assert localize_event([tiny], META, VisionConfig()) is None


def test_lateral_and_scale_measurements():
    track = Track(1, "car", [det(i, box=(100 + 20 * i, 100, 140 + 20 * i, 140 + 4 * i)) for i in range(5)])
    shift, = lateral_shifts([track], 0.0, 0.4, 640)
    assert shift.shift_fraction == pytest.approx(80 / 640)
    change, = scale_changes([track], 0.0, 0.4)
    assert change.area_ratio == pytest.approx((40 * 56) / (40 * 40))
    assert lateral_shifts([track], 5.0, 6.0, 640) == []


def test_signal_summary_never_infers_change():
    track = Track(1, "traffic light", [det(i, "traffic light") for i in range(5)])
    states = dict(zip(track.detections, ["red", "red", "green", "green", "green"]))
    assert summarize_signal(track, states).state == "unknown"
    states = dict(zip(track.detections, ["green", "green", "green", "unknown", "green"]))
    assert summarize_signal(track, states).state == "green"
    states = dict(zip(track.detections, ["green", "unknown", "unknown", "unknown", "green"]))
    assert summarize_signal(track, states).state == "unknown"  # no clear majority


def test_signal_color_from_pixels():
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    image = np.zeros((60, 40, 3), dtype=np.uint8)
    d = det(0, "traffic light", (10, 5, 30, 55))
    assert estimate_signal_color(image, d) == "unknown"          # dark housing only
    image[40:52, 14:26] = (40, 230, 40)                           # lit green lamp (BGR)
    assert estimate_signal_color(image, d) == "green"
    image[8:20, 14:26] = (30, 30, 240)                            # red also lit -> ambiguous
    assert estimate_signal_color(image, d) == "unknown"
    assert estimate_signal_color(None, d) == "unknown"
