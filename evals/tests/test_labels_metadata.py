"""Hugging Face `metadata.csv` label layout (file_name instead of id)."""
import pytest

from witness_evals import load_labels


def test_file_name_column_yields_padded_ids(tmp_path):
    path = tmp_path / "metadata.csv"
    path.write_text("file_name,time_of_event,time_of_alert,light_conditions,weather,scene,time_to_accident\n"
                    "00822.mp4,19.5,18.633,Normal,Cloudy,Urban,\n"
                    "00000.mp4,20.76,19.136,Normal,Clear,Urban,\n")
    labels = load_labels(path)
    assert [c.id for c in labels] == ["00822", "00000"]
    assert labels[1].time_of_event == 20.76 and labels[1].time_of_alert == 19.136 and labels[1].target is None


def test_id_column_wins_when_both_present(tmp_path):
    path = tmp_path / "both.csv"
    path.write_text("id,file_name,time_of_event\nclip-a,00000.mp4,1.5\n")
    assert [c.id for c in load_labels(path)] == ["clip-a"]


def test_neither_id_nor_file_name_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("name,time_of_event\nx,1\n")
    with pytest.raises(ValueError, match="file_name"):
        load_labels(path)
