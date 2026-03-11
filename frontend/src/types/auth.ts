export type AuthUserDTO = {
  id: number;
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  role?: string | null;
  phone_verified: boolean;
  email_verified: boolean;
  created_at?: string | null;
};

export type AuthMeResponse = {
  ok: boolean;
  user: AuthUserDTO;
};

export type AuthTokenUserResponse = {
  ok: boolean;
  token?: string | null;
  user: AuthUserDTO;
};
