import { IconDeviceMobile, IconX } from "@tabler/icons-react";
import { useEffect, useState } from "react";

const DISMISSED_KEY = "kj_install_dismissed";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Chrome/Android only — iOS Safari never fires `beforeinstallprompt`, so
 * this simply never appears there, which is an acceptable platform gap. */
export default function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(wasDismissed);

  useEffect(() => {
    function onBeforeInstall(event: Event) {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    }
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, []);

  function dismiss() {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      /* private browsing — banner just reappears next visit */
    }
  }

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
    dismiss();
  }

  if (!deferred || dismissed) return null;

  return (
    <div className="fixed inset-x-0 bottom-16 z-30 px-4 sm:bottom-4">
      <div className="mx-auto flex max-w-md items-center gap-3 rounded-xl border border-neutral-200 bg-white p-3 shadow-lg">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-wash text-teal">
          <IconDeviceMobile size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-neutral-900">Install Krishna Jewellers</p>
          <p className="text-xs text-neutral-600">Add to your home screen for quick access.</p>
        </div>
        <button type="button" onClick={install} className="btn-primary shrink-0 px-4 text-sm">
          Install
        </button>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss"
          className="shrink-0 rounded-lg p-1.5 text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-600"
        >
          <IconX size={18} />
        </button>
      </div>
    </div>
  );
}
