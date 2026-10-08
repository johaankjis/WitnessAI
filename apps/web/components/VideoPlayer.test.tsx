import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import VideoPlayer from "./VideoPlayer";

describe("VideoPlayer", () => {
  it("labels mock:// URIs as non-playable and still tracks the seek target", () => {
    const onSeeked = vi.fn();
    const { rerender } = render(
      <VideoPlayer
        videoUri="mock://demo-001/no-video"
        durationSeconds={20}
        seekToSeconds={null}
        seekToken={0}
        onSeeked={onSeeked}
      />,
    );
    expect(screen.getByTestId("video-player")).toHaveAttribute("data-playable", "false");
    expect(screen.getByText("No playable footage")).toBeInTheDocument();
    expect(screen.queryByTestId("video-element")).not.toBeInTheDocument();

    rerender(
      <VideoPlayer
        videoUri="mock://demo-001/no-video"
        durationSeconds={20}
        seekToSeconds={8}
        seekToken={1}
        onSeeked={onSeeked}
      />,
    );
    expect(screen.getByTestId("video-time-readout")).toHaveTextContent("0:08.0");
    expect(screen.getByTestId("video-player")).toHaveAttribute("data-current-time", "8.0");
    expect(onSeeked).toHaveBeenCalledWith(8);
  });

  it("renders a real <video> element for media URLs and seeks on token change", () => {
    const onSeeked = vi.fn();
    const { rerender } = render(
      <VideoPlayer
        videoUri="https://cdn.example/clip.mp4"
        durationSeconds={20}
        seekToSeconds={null}
        seekToken={0}
        onSeeked={onSeeked}
      />,
    );
    expect(screen.getByTestId("video-element")).toHaveAttribute(
      "src",
      "https://cdn.example/clip.mp4",
    );

    rerender(
      <VideoPlayer
        videoUri="https://cdn.example/clip.mp4"
        durationSeconds={20}
        seekToSeconds={12}
        seekToken={1}
        onSeeked={onSeeked}
      />,
    );
    expect(onSeeked).toHaveBeenCalledWith(12);
    expect(screen.getByTestId("video-time-readout")).toHaveTextContent("0:12.0");
  });

  it("clamps seek targets to the incident duration", () => {
    const onSeeked = vi.fn();
    render(
      <VideoPlayer
        videoUri="mock://demo-001/no-video"
        durationSeconds={20}
        seekToSeconds={99}
        seekToken={1}
        onSeeked={onSeeked}
      />,
    );
    expect(onSeeked).toHaveBeenCalledWith(20);
    expect(screen.getByTestId("video-time-readout")).toHaveTextContent("0:20.0");
  });
});
