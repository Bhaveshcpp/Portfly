import { NavLink, Route, Routes } from "react-router-dom";
import Chat from "./Chat.jsx";
import Dashboard from "./Dashboard.jsx";

export default function App() {
  return (
    <div className="shell">
      <aside className="nav">
        <h1>Portfly</h1>
        <NavLink to="/" end>
          WhatsApp
        </NavLink>
        <NavLink to="/desk">Business desk</NavLink>
      </aside>
      <div className="main">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/desk" element={<Dashboard />} />
        </Routes>
      </div>
    </div>
  );
}
