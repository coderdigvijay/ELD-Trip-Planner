import { setupServer } from "msw/node";

/** Shared MSW server. Tests register handlers per case with server.use(...). */
export const server = setupServer();

export const errorBody = (code: string, message: string, extra: Record<string, unknown> = {}) => ({
  error: { code, message, request_id: "7f3c2a9e1b4d4c0e", ...extra },
});
