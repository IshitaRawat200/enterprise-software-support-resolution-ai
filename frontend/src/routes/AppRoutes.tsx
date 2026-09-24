import { Navigate, Route, Routes } from "react-router-dom";

import Login from "../pages/Login";
import Dashboard from "../pages/Dashboard";
import Chat from "../pages/Chat";
import Tickets from "../pages/Tickets";
import TicketDetails from "../pages/TicketDetails";
import KnowledgeBase from "../pages/KnowledgeBase";
import Account from "../pages/Account";
import AdminDashboard from "../pages/admin/AdminDashboard";

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={<Login />}
      />

      <Route
        path="/dashboard"
        element={<Dashboard />}
      />

      <Route
        path="/chat"
        element={<Chat />}
      />

      <Route
        path="/tickets"
        element={<Tickets />}
      />

      <Route
        path="/tickets/:ticketId"
        element={<TicketDetails />}
      />

      <Route
        path="/knowledge-base"
        element={<KnowledgeBase />}
      />

      <Route
        path="/admin"
        element={<AdminDashboard />}
      />

      <Route
        path="/account"
        element={<Account />}
      />

      <Route
        path="/"
        element={
          <Navigate
            to="/dashboard"
            replace
          />
        }
      />

      <Route
        path="*"
        element={
          <Navigate
            to="/dashboard"
            replace
          />
        }
      />
    </Routes>
  );
}

export default AppRoutes;