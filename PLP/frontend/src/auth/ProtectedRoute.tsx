import { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useSession } from "./SessionProvider";

interface ProtectedRouteProps extends PropsWithChildren {
  adminOnly?: boolean;
}

export function ProtectedRoute({ children, adminOnly = false }: ProtectedRouteProps) {
  const { user, loading } = useSession();
  const location = useLocation();

  if (loading) {
    return <div className="state-card">Checking access...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (adminOnly && !user.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
