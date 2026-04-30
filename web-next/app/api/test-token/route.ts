import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

export async function GET(request: NextRequest) {
  const secret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "";
  try {
    const token = await getToken({ req: request, secret });
    return NextResponse.json({
      hasToken: !!token,
      tokenKeys: token ? Object.keys(token) : [],
      hasAccessToken: !!(token as any)?.access_token,
      accessTokenPrefix: (token as any)?.access_token ? ((token as any).access_token as string).substring(0, 10) + "..." : null,
    });
  } catch (error: unknown) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : String(error),
    }, { status: 500 });
  }
}
