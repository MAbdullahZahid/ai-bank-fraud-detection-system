import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const isAdmin = !!localStorage.getItem("admin_token");
  const isUser = !!localStorage.getItem("user_token");

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const clearSession = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("user_token");
  };

  const goHome = () => {
    clearSession();
  };

  const logoutUser = () => {
    clearSession();
    navigate("/login");
  };

  const logoutAdmin = () => {
    clearSession();
    navigate("/admin/login");
  };

  const isActive = (path) => location.pathname === path;

  return (
    <div className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand" onClick={goHome}>
          <span className="brand-mark">AI</span>
          <span className="brand-text">AI Bank Fraud Detection</span>
        </Link>

        <button
          type="button"
          className="nav-toggle"
          onClick={() => setMenuOpen((value) => !value)}
          aria-label="Toggle menu"
        >
          <span />
          <span />
          <span />
        </button>

        <div className={`nav-links ${menuOpen ? "open" : ""}`}>
          <div className="nav-group">
            <Link to="/" className={isActive("/") ? "active" : ""} onClick={goHome}>
              Home
            </Link>
            {isUser && (
              <Link to="/transfer" className={isActive("/transfer") ? "active" : ""}>
                Console
              </Link>
            )}
            {isAdmin && (
              <Link
                to="/admin/dashboard"
                className={location.pathname.startsWith("/admin/dashboard") ? "active" : ""}
              >
                Dashboard
              </Link>
            )}
          </div>

          <div className="nav-group">
            {isUser ? (
              <Link to="/transfer" className={`nav-action ${isActive("/transfer") ? "active" : ""}`}>
                Customer dashboard
              </Link>
            ) : (
            <Link
  to="/login"
  className={`nav-action ${isActive("/login") ? "active" : ""}`}
  onClick={() => {
    localStorage.removeItem("admin_token");
  }}
>
  Customer login
</Link>
            )}
          </div>

          <div className="nav-group">
            {isAdmin ? (
              <button type="button" className="nav-action danger" onClick={logoutAdmin}>
                Logout
              </button>
            ) : (
              <Link
  to="/admin/login"
  className={`nav-action ${isActive("/admin/login") ? "active" : ""}`}
  onClick={() => {
    localStorage.removeItem("user_token");
  }}
>
  Admin login
</Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
