import { Link, useLocation, useNavigate } from "react-router-dom";

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const isAdmin = !!localStorage.getItem("admin_token");

  const logout = () => {
    localStorage.removeItem("admin_token");
    navigate("/admin/login");
  };

  return (
    <div className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">L</span>
          Ledger
        </Link>
        <div className="nav-links">
          <Link to="/" className={location.pathname === "/" ? "active" : ""}>
            Send a transfer
          </Link>
          {isAdmin ? (
            <>
              <Link
                to="/admin/dashboard"
                className={location.pathname.startsWith("/admin/dashboard") ? "active" : ""}
              >
                Admin portal
              </Link>
              <button onClick={logout}>Log out</button>
            </>
          ) : (
            <Link
              to="/admin/login"
              className={location.pathname === "/admin/login" ? "active" : ""}
            >
              Admin login
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
