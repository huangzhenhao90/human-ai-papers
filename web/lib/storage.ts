"use client";

const FAVORITES_KEY = "human-ai-papers-favorites-v1";
const READ_KEY = "human-ai-papers-read-v1";
const FAVORITES_EVENT = "human-ai-papers:favorites";
const READ_EVENT = "human-ai-papers:read";

function readSet(key: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(key);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id): id is string => typeof id === "string"));
  } catch {
    return new Set();
  }
}

function writeSet(key: string, event: string, ids: Set<string>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(Array.from(ids)));
  window.dispatchEvent(new CustomEvent(event, { detail: ids.size }));
}

export function readFavorites() {
  return readSet(FAVORITES_KEY);
}

export function toggleFavorite(id: string) {
  const ids = readFavorites();
  if (ids.has(id)) ids.delete(id);
  else ids.add(id);
  writeSet(FAVORITES_KEY, FAVORITES_EVENT, ids);
  return ids.has(id);
}

export function readReadIds() {
  return readSet(READ_KEY);
}

export function markRead(id: string) {
  const ids = readReadIds();
  if (ids.has(id)) return;
  ids.add(id);
  const limited = new Set(Array.from(ids).slice(-5000));
  writeSet(READ_KEY, READ_EVENT, limited);
}

export const storageEvents = {
  favorites: FAVORITES_EVENT,
  read: READ_EVENT,
};
