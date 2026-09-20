import { useEffect, useRef, useState } from "react";

import { useAuth } from "../auth/AuthContext";

const IDLE_LIMIT_MS = 15 * 60 * 1000;
const WARN_AT_MS = 14 * 60 * 1000;
const ACTIVITY_EVENTS = ["pointerdown", "touchstart", "keydown", "scroll", "wheel"] as const;

/** Signs the user out after 15 minutes without a tap, scroll or keypress,
 * with a warning at 14. Mounted inside AppShell, so it only exists while
 * someone is signed in.
 *
 * Elapsed time is measured against Date.now() rather than counted in timer
 * ticks: a locked phone or backgrounded tab throttles or freezes timers,
 * but the wall clock keeps going, so switching apps can't stall the
 * countdown. The check also runs the moment the page becomes visible
 * again, before any activity event from returning can reset it. */
export default function IdleTimeout() {
  const { signOut } = useAuth();
  const lastActivity = useRef(Date.now());
  const [warning, setWarning] = useState(false);

  useEffect(() => {
    function idleFor() {
      return Date.now() - lastActivity.current;
    }

    function check() {
      const idle = idleFor();
      if (idle >= IDLE_LIMIT_MS) signOut();
      else setWarning(idle >= WARN_AT_MS);
    }

    function onActivity() {
      // A tap on returning to an app that was already past the limit must
      // not rescue the session.
      if (idleFor() >= IDLE_LIMIT_MS) {
        signOut();
        return;
      }
      lastActivity.current = Date.now();
      setWarning(false);
    }

    function onVisible() {
      if (document.visibilityState === "visible") check();
    }

    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, onActivity, { capture: true, passive: true }));
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pageshow", check);
    window.addEventListener("focus", check);
    const timer = window.setInterval(check, 1000);

    return () => {
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, onActivity, { capture: true }));
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pageshow", check);
      window.removeEventListener("focus", check);
      window.clearInterval(timer);
    };
  }, [signOut]);

  if (!warning) return null;

  return (
    <div className="fixed inset-x-0 top-16 z-50 px-4" role="alertdialog" aria-live="assertive">
      <div className="mx-auto flex max-w-md items-center gap-3 rounded-xl border border-gold/40 bg-white p-3 shadow-lg">
        <p className="min-w-0 flex-1 text-sm text-neutral-800">
          You'll be signed out in 1 minute due to inactivity.
        </p>
        <button
          type="button"
          className="btn-primary shrink-0 px-4 text-sm"
          onClick={() => {
            lastActivity.current = Date.now();
            setWarning(false);
          }}
        >
          Stay signed in
        </button>
      </div>
    </div>
  );
}
