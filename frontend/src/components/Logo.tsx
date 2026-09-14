import markReversed from "../assets/krishna-jewellers-mark-reversed.svg";
import logoFull from "../assets/krishna-jewellers-logo-full.svg";
import logoReversed from "../assets/krishna-jewellers-logo-reversed.svg";

/**
 * Brand lockups. `reversed` is the white artwork, for the teal app bar;
 * `full` is the colour version, for white backgrounds.
 *
 * On the app bar the lockup would crowd the screen title on a phone, so
 * only the feather mark shows on narrow viewports and the full lockup
 * appears from `sm` upwards.
 */
export function AppBarLogo() {
  return (
    <>
      <img
        src={markReversed}
        alt="Krishna Jewellers"
        className="h-8 w-auto shrink-0 sm:hidden"
        width={112}
        height={120}
      />
      <img
        src={logoReversed}
        alt="Krishna Jewellers"
        className="hidden h-9 w-auto shrink-0 sm:block"
        width={320}
        height={120}
      />
    </>
  );
}

export function FullLogo({ className = "" }: { className?: string }) {
  return (
    <img
      src={logoFull}
      alt="Krishna Jewellers"
      className={className}
      width={320}
      height={120}
    />
  );
}
