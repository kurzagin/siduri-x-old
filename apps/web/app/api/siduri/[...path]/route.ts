import { NextRequest } from "next/server";

const ORCHESTRATOR_URL = process.env.SIDURI_ORCHESTRATOR_URL ?? "http://127.0.0.1:8765";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const incoming = new URL(request.url);
  const upstream = new URL(`/${path.map(encodeURIComponent).join("/")}`, ORCHESTRATOR_URL);
  upstream.search = incoming.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  headers.set("Origin", "http://127.0.0.1:3000");

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    const responseType = response.headers.get("content-type");
    if (responseType) responseHeaders.set("Content-Type", responseType);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    return Response.json(
      { error: "Siduri orchestrator is unavailable.", detail: String(error) },
      { status: 502 },
    );
  }
}

export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;

