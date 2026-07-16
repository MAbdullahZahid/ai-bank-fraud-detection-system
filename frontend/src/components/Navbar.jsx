import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  // Re-check tokens on every render (location change triggers this) so the
  // navbar never shows stale login/logout state after navigating.
  const isAdmin = !!localStorage.getItem("admin_token");
  const isUser = !!localStorage.getItem("user_token");

  // Close the mobile menu whenever the route changes
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const logoutAdmin = () => {
    localStorage.removeItem("admin_token");
    navigate("/admin/login");
  };

  const logoutUser = () => {
    localStorage.removeItem("user_token");
    navigate("/login");
  };

  const isActive = (path) => location.pathname === path;

  return (
    <div className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">AI</span>
          AI Bank Fraud Detection
        </Link>

        <button
          className="nav-toggle"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <div className={`nav-links ${menuOpen ? "open" : ""}`}>
          <div className="nav-group">
            <Link to="/" className={isActive("/") ? "active" : ""}>
              Home
            </Link>
          </div>

          <div className="nav-group">
            {isUser ? (
              <>
                <Link to="/transfer" className={isActive("/transfer") ? "active" : ""}>
                  Transfer
                </Link>
                <button onClick={logoutUser}>Customer log out</button>
              </>
            ) : (
              <Link to="/login" className={isActive("/login") ? "active" : ""}>
                Customer login
              </Link>
            )}
          </div>

          <div className="nav-group">
            {isAdmin ? (
              <>
                <Link
                  to="/admin/dashboard"
                  className={location.pathname.startsWith("/admin/dashboard") ? "active" : ""}
                >
                  Admin portal
                </Link>
                <button onClick={logoutAdmin}>Admin log out</button>
              </>
            ) : (
              <Link to="/admin/login" className={isActive("/admin/login") ? "active" : ""}>
                Admin login
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
