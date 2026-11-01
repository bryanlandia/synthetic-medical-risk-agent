"use client";

import { createContext, useContext, useEffect, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import policy from "@/content/pet_ct_policy.json";
import { clear, initial, isFresh, load, reduce, save, type Action, type Saved } from "@/lib/store";

type Ctx = { saved: Saved; dispatch: Dispatch<Action>; hydrated: boolean; casesHash: string; policyId: string };
const Review = createContext<Ctx | null>(null);

export const POLICY_ID: string = policy.id;

export function useReview(): Ctx {
  const ctx = useContext(Review);
  if (!ctx) throw new Error("useReview must be used inside ReviewProvider");
  return ctx;
}

/** Holds the progress. The first render is always the fresh state (it matches the server); saved progress is read after mount. */
export function ReviewProvider({ casesHash, children }: { casesHash: string; children: ReactNode }) {
  const [saved, dispatch] = useReducer(reduce, undefined, () => initial(casesHash, POLICY_ID));
  const first = useRef(saved);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    dispatch({ type: "hydrate", saved: load(window.localStorage, casesHash, POLICY_ID) });
    setHydrated(true);
  }, [casesHash]);

  useEffect(() => {
    // while the state is still the object it started as, nothing has been read or changed: writing it would erase saved progress
    if (saved === first.current) return;
    if (isFresh(saved)) clear(window.localStorage);
    else save(window.localStorage, saved);
  }, [saved]);

  return <Review.Provider value={{ saved, dispatch, hydrated, casesHash, policyId: POLICY_ID }}>{children}</Review.Provider>;
}
