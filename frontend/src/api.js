import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

// Admin and User are separate identities with separate tokens.
// Call sites pass which one a request needs.
export const authHeader = (kind) => {
  const key = kind === "admin" ? "admin_token" : "user_token";
  const token = localStorage.getItem(key);
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export default api;
