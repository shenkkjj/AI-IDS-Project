"use client";

interface EyeBallProps {
  size?: string;
  pupilSize?: string;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
}

export default function EyeBall({
  size = "48px",
  pupilSize = "16px",
  maxDistance = 10,
  eyeColor = "white",
  pupilColor = "black",
}: EyeBallProps) {
  return (
    <div
      className="eyeball"
      data-max-distance={maxDistance}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        backgroundColor: eyeColor,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        willChange: "height",
      }}
    >
      <div
        className="eyeball-pupil"
        style={{
          width: pupilSize,
          height: pupilSize,
          borderRadius: "50%",
          backgroundColor: pupilColor,
          willChange: "transform",
        }}
      />
    </div>
  );
}
