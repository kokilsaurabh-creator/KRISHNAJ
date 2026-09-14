import { PRESET_LABELS, rangeForPreset, type DateRange, type PresetKey } from "../lib/dates";

const PRESETS: PresetKey[] = ["this_month", "this_fy", "last_fy", "custom"];

export default function DateRangePicker({
  preset,
  range,
  onChange,
}: {
  preset: PresetKey;
  range: DateRange;
  onChange: (preset: PresetKey, range: DateRange) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((key) => {
          const selected = preset === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() => onChange(key, key === "custom" ? range : rangeForPreset(key))}
              className={`min-h-[40px] rounded-full border px-4 py-1.5 text-sm transition ${
                selected
                  ? "border-teal bg-teal-wash font-medium text-teal"
                  : "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400"
              }`}
            >
              {PRESET_LABELS[key]}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="from-date" className="mb-1 block text-xs font-medium text-neutral-600">
            From
          </label>
          <input
            id="from-date"
            type="date"
            className="field"
            value={range.from}
            onChange={(e) => onChange("custom", { ...range, from: e.target.value })}
          />
        </div>
        <div>
          <label htmlFor="to-date" className="mb-1 block text-xs font-medium text-neutral-600">
            To
          </label>
          <input
            id="to-date"
            type="date"
            className="field"
            value={range.to}
            onChange={(e) => onChange("custom", { ...range, to: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}
