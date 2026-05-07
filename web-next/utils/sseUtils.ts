export function parseSseBuffer(rawBuffer: string): { events: { event: string; dataText: string }[]; rest: string } {
  const events: { event: string; dataText: string }[] = [];
  let rest = rawBuffer.replaceAll("\r\n", "\n");

  while (true) {
    const boundary = rest.indexOf("\n\n");
    if (boundary < 0) {
      break;
    }

    const block = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);

    const lines = block
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line);

    if (lines.length === 0) {
      continue;
    }

    let event = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    events.push({ event, dataText: dataLines.join("\n") });
  }

  return { events, rest };
}

export function parseSseJson(dataText: string): Record<string, unknown> {
  const text = String(dataText || "").trim();
  if (!text) {
    return {};
  }
  try {
    const parsed = JSON.parse(text) as Record<string, unknown>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}
