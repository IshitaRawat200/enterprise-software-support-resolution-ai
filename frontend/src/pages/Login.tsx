import { useState } from "react";
import type { FormEvent } from "react";
import { login } from "../services/authService";
import "./Login.css";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      const loginData = await login({
        email,
        password,
      });

      // Save authentication token
      localStorage.setItem(
        "eris_access_token",
        loginData.access_token
      );

      // Save email for frontend display
      localStorage.setItem(
        "eris_user_email",
        email
      );

      // Go directly to dashboard
      window.location.href = "/dashboard";
    } catch (err) {
      localStorage.removeItem("eris_access_token");
      localStorage.removeItem("eris_user_email");

      setError(
        err instanceof Error
          ? err.message
          : "Unable to sign in. Please check your credentials."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">
            E
          </div>

          <div>
            <h1>ERIS</h1>
            <p>
              Enterprise Resolution Intelligence System
            </p>
          </div>
        </div>

        <div className="login-heading">
          <h2>Welcome back</h2>
          <p>
            Sign in to access your support workspace.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">
              Email address
            </label>

            <input
              id="email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              autoComplete="email"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">
              Password
            </label>

            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Signing in..."
              : "Sign in"}
          </button>
        </form>

        <div className="login-footer">
          <p>
            Secure enterprise support powered by AI,
            RAG and intelligent escalation.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;