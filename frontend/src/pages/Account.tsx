import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getProfile,
  type ProfileResponse,
} from "../services/customerService";
import AppLayout from "../components/layout/AppLayout";
import "./Account.css";

function Account() {
  const navigate = useNavigate();

  const [profile, setProfile] =
    useState<ProfileResponse | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      const token =
        localStorage.getItem(
          "eris_access_token"
        );

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        setError("");

        const data = await getProfile();

        if (!cancelled) {
          setProfile(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.error(
            "Failed to load account:",
            err
          );

          const message =
            err instanceof Error
              ? err.message
              : "Unable to load account information.";

          setError(message);

          if (
            message.includes("401") ||
            message
              .toLowerCase()
              .includes("unauthorized")
          ) {
            localStorage.removeItem(
              "eris_access_token"
            );

            localStorage.removeItem(
              "eris_user_email"
            );

            navigate("/login");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadProfile();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function handleLogout() {
    localStorage.removeItem(
      "eris_access_token"
    );

    localStorage.removeItem(
      "eris_user_email"
    );

    window.location.href = "/login";
  }

  function displayValue(
    value: string | null | undefined
  ) {
    return value || "—";
  }

  const user = profile?.user;
  const customer = profile?.customer;

  return (
    <AppLayout onLogout={handleLogout}>
      <section className="account-content">

        {loading && (
          <div className="customer-card">
            <div className="account-loading">
              <div className="account-loading-icon">
                ◷
              </div>

              <strong>
                Loading account information...
              </strong>

              <p>
                Fetching your account details.
              </p>
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="customer-card">
            <div className="account-error">
              <h3>
                Unable to load account
              </h3>

              <p>{error}</p>

              <button
                type="button"
                className="customer-secondary-button"
                onClick={() =>
                  window.location.reload()
                }
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {!loading &&
          !error &&
          profile && (
            <>
              <section className="customer-card account-card">
                <div className="customer-card-header">
                  <div>
                    <h3>
                      User Information
                    </h3>

                    <p>
                      Your authenticated account
                    </p>
                  </div>
                </div>

                <div className="account-info-grid">
                  <div className="account-info-item">
                    <span>Email</span>

                    <strong>
                      {displayValue(
                        user?.email
                      )}
                    </strong>
                  </div>

                  <div className="account-info-item">
                    <span>Role</span>

                    <strong>
                      {displayValue(
                        user?.role
                      )}
                    </strong>
                  </div>

                  <div className="account-info-item">
                    <span>Status</span>

                    <strong>
                      {user?.is_active
                        ? "Active"
                        : "Inactive"}
                    </strong>
                  </div>

                  <div className="account-info-item">
                    <span>User ID</span>

                    <strong>
                      {displayValue(
                        user?.id
                      )}
                    </strong>
                  </div>
                </div>
              </section>

              {customer && (
                <section className="customer-card account-card">
                  <div className="customer-card-header">
                    <div>
                      <h3>
                        Customer Account
                      </h3>

                      <p>
                        Your enterprise support
                        account
                      </p>
                    </div>
                  </div>

                  <div className="account-info-grid">
                    <div className="account-info-item">
                      <span>
                        Customer Code
                      </span>

                      <strong>
                        {displayValue(
                          customer.customer_code
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>
                        Contact Name
                      </span>

                      <strong>
                        {displayValue(
                          customer.contact_name
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>Company</span>

                      <strong>
                        {displayValue(
                          customer.company_name
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>Industry</span>

                      <strong>
                        {displayValue(
                          customer.industry
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>Region</span>

                      <strong>
                        {displayValue(
                          customer.region
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>
                        Account Status
                      </span>

                      <strong>
                        {displayValue(
                          customer.account_status
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>
                        Subscription
                      </span>

                      <strong>
                        {displayValue(
                          customer.subscription_tier
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>SLA</span>

                      <strong>
                        {displayValue(
                          customer.sla_level
                        )}
                      </strong>
                    </div>

                    <div className="account-info-item">
                      <span>
                        Renewal Date
                      </span>

                      <strong>
                        {displayValue(
                          customer.renewal_date
                        )}
                      </strong>
                    </div>
                  </div>
                </section>
              )}

              {!customer && (
                <section className="customer-card account-card">
                  <div className="account-empty-state">
                    <strong>
                      No customer account linked
                    </strong>

                    <p>
                      This user does not currently
                      have a customer account.
                    </p>
                  </div>
                </section>
              )}
            </>
          )}

      </section>
    </AppLayout>
  );
}

export default Account;