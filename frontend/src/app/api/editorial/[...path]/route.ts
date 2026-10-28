import { NextRequest, NextResponse } from "next/server";
import { createProxyResponse, fetchBackend } from "@/server/backend-api";
import { getServerSession } from "@/server/session";

type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const session = await getServerSession();
  if (!session?.user?.id) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { path } = await context.params;
  if (path.some((part) => !/^[A-Za-z0-9_.-]+$/.test(part) || part === "." || part === "..")) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }
  const suffix = path.map(encodeURIComponent).join("/");
  const upstream = await fetchBackend(`/editorial/${suffix}${request.nextUrl.search}`, {
    method: request.method,
    userId: session.user.id,
    cache: "no-store",
    headers: {
      ...(request.headers.get("content-type") ? { "content-type": request.headers.get("content-type")! } : {}),
      ...(request.headers.get("range") ? { range: request.headers.get("range")! } : {}),
    },
    ...(request.method === "GET" ? {} : { body: await request.arrayBuffer() }),
  });
  return createProxyResponse(upstream);
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
