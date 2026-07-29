const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function extractErrorMessage(payload, status) {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((error) => error.msg || "Invalid request")
      .join(", ");
  }

  return `Extraction failed with HTTP ${status}.`;
}

export async function extractFiling(url) {
  const response = await fetch(`${API_BASE_URL}/api/v1/extractions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.status));
  }

  return payload;
}
