/** Daily return loop — streak, ritual, resume. Local only. */

export function todayKey(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

export function yesterdayKey(d = new Date()) {
  const y = new Date(d);
  y.setDate(y.getDate() - 1);
  return y.toISOString().slice(0, 10);
}

export function nextStreak(lastVisit: string | null, streak: number, now = new Date()) {
  const today = todayKey(now);
  if (lastVisit === today) return { streak, lastVisit, touched: false };
  if (lastVisit === yesterdayKey(now)) return { streak: streak + 1, lastVisit: today, touched: true };
  return { streak: 1, lastVisit: today, touched: true };
}

export const RITUALS = [
  { id: "name", label: "Name the real constraint", view: "talk" as const },
  { id: "goal", label: "Hold the weekly goal", view: "home" as const },
  { id: "write", label: "One honest sentence of story", view: "write" as const },
  { id: "build", label: "Advance one builder stage", view: "build" as const },
];
