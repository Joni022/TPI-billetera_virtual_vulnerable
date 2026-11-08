import type {
  ApiErrorPayload,
  ApiResult,
  LabRun,
  LabStatus,
  WalletMeta,
} from "./types";

export class HttpError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.payload = payload;
  }
}

async function decodeResponse<T>(response: Response): Promise<ApiResult<T>> {
  const bodyText = await response.text();
  let payload: unknown = null;
  if (bodyText) {
    try {
      payload = JSON.parse(bodyText) as unknown;
    } catch {
      payload = bodyText;
    }
  }

  if (!response.ok) {
    const errorMessage =
      typeof payload === "object" && payload !== null && "error" in payload
        ? String((payload as ApiErrorPayload).error ?? "No se pudo completar la solicitud.")
        : "No se pudo completar la solicitud.";
    throw new HttpError(errorMessage, response.status, payload);
  }

  return { data: payload as T, status: response.status };
}

export async function walletRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  return decodeResponse<T>(response);
}

export async function walletPost<T>(
  path: string,
  body: unknown,
): Promise<ApiResult<T>> {
  const tokenResult = await walletRequest<{ token: string }>("/api/csrf-token");
  return walletRequest<T>(path, {
    method: "POST",
    headers: { "X-CSRF-Token": tokenResult.data.token },
    body: JSON.stringify(body),
  });
}

export async function readWalletMeta(): Promise<WalletMeta> {
  const result = await walletRequest<WalletMeta>("/api/meta");
  return result.data;
}

export async function labRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  return decodeResponse<T>(response);
}

export async function labPost<T>(
  path: string,
  body: unknown,
): Promise<ApiResult<T>> {
  const tokenResult = await labRequest<{ token: string }>("/lab/api/csrf-token");
  return labRequest<T>(path, {
    method: "POST",
    headers: { "X-CSRF-Token": tokenResult.data.token },
    body: JSON.stringify(body),
  });
}

export async function getLabStatus(): Promise<LabStatus> {
  const response = await labRequest<LabStatus>("/lab/api/status");
  return response.data;
}

export async function getLabRuns(): Promise<{ runs: LabRun[] }> {
  const response = await labRequest<{ runs: LabRun[] }>("/lab/api/runs");
  return response.data;
}

export async function getLabRun(id: string): Promise<LabRun> {
  const response = await labRequest<LabRun>("/lab/api/runs/" + encodeURIComponent(id));
  return response.data;
}
