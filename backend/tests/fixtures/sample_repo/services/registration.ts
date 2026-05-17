import { createUser } from "../db/users";

export async function registerUser(email: string) {
  const user = await createUser(email);
  return user;
}

