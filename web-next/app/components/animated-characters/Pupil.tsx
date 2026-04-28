"use client";

interface PupilProps {
  size?: string;
  maxDistance?: number;
  pupilColor?: string;
}

export default function Pupil({
  size = "12px",
  maxDistance = 5,
  pupilColor = "black",
}: PupilProps) {
  return (
    <div
      data-max-distance={maxDistance}
      className="pupil"
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        backgroundColor: pupilColor,
        willChange: "transform",
      }}
    />
  );
}
