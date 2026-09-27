import { useCallback, useEffect, useState } from "react";
import HomePage from "./pages/HomePage";
import JobPage from "./pages/JobPage";

/**
 * Two screens, no nesting, no data loaders shared across routes — a real
 * router (react-router) would be pure overhead here. A minimal
 * History-API switch keeps the URL bookmarkable (job pages are shareable
 * links a data steward could paste to a teammate) without adding a dependency.
 */
export default function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((to: string) => {
    window.history.pushState(null, "", to);
    setPath(to);
  }, []);

  const jobMatch = path.match(/^\/jobs\/([^/]+)$/);

  return (
    <div className="min-h-screen bg-paper text-ink">
      {jobMatch ? (
        <JobPage jobId={jobMatch[1]} onNavigate={navigate} />
      ) : (
        <HomePage onNavigate={navigate} />
      )}
    </div>
  );
}
